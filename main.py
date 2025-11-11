URRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from extractors.listing_parser import scrape_search_url  # type: ignore
from extractors.delta_mode import annotate_with_delta  # type: ignore
from utils.url_handler import read_urls_from_file, normalize_url  # type: ignore
from outputs.export_manager import export_data  # type: ignore

def load_settings(settings_path: str) -> Dict[str, Any]:
    if not os.path.exists(settings_path):
        logging.warning("Settings file %s not found. Using defaults.", settings_path)
        return {}

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logging.info("Loaded settings from %s", settings_path)
        return data
    except Exception as exc:
        logging.error("Failed to load settings from %s: %s", settings_path, exc)
        return {}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Immobiliare.it Listing Page Scraper (by search URL)"
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default="data/inputs.sample.txt",
        help="Path to a text file containing search URLs (one per line).",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Single Immobiliare.it search URL (overrides --input-file).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/output.json",
        help="Output file path (extension used to determine format if --format is omitted).",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "csv", "html"],
        default=None,
        help="Output format. If omitted, inferred from output file extension.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of result pages to scrape per URL. Overrides settings file.",
    )
    parser.add_argument(
        "--delta-base",
        type=str,
        default=None,
        help="Path to previous run JSON file for Delta Mode comparison.",
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=os.path.join(CURRENT_DIR, "config", "settings.example.json"),
        help="Path to settings JSON file.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    return parser.parse_args()

def infer_format_from_output(output_path: str) -> str:
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".csv":
        return "csv"
    if ext in (".htm", ".html"):
        return "html"
    return "json"

def load_previous_run(path: str) -> List[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        logging.info("No previous run file found at %s", path)
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logging.warning("Previous run file %s does not contain a list.", path)
            return []
        logging.info("Loaded %d items from previous run file.", len(data))
        return data
    except Exception as exc:
        logging.error("Failed to load previous run file %s: %s", path, exc)
        return []

def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    settings = load_settings(args.settings)
    scraper_settings: Dict[str, Any] = settings.get("scraper", {})
    output_settings: Dict[str, Any] = settings.get("output", {})
    delta_settings: Dict[str, Any] = settings.get("delta_mode", {})

    max_pages: Optional[int] = args.max_pages or scraper_settings.get("max_pages", 1)

    # Determine URLs
    urls: List[str] = []
    if args.url:
        urls = [normalize_url(args.url)]
    else:
        urls = [normalize_url(u) for u in read_urls_from_file(args.input_file)]

    if not urls:
        logging.error("No URLs provided. Use --url or --input-file.")
        sys.exit(1)

    logging.info("Starting scrape for %d URL(s).", len(urls))

    all_items: List[Dict[str, Any]] = []
    for url in urls:
        try:
            logging.info("Scraping URL: %s", url)
            items = scrape_search_url(
                url=url,
                max_pages=max_pages,
                user_agent=scraper_settings.get("user_agent"),
                timeout=scraper_settings.get("timeout", 20),
                parallel_requests=scraper_settings.get("parallel_requests", 4),
            )
            logging.info("Scraped %d listings from URL: %s", len(items), url)
            all_items.extend(items)
        except Exception as exc:
            logging.error("Error scraping URL %s: %s", url, exc)

    logging.info("Total listings before delta processing: %d", len(all_items))

    # Delta Mode
    delta_enabled = bool(delta_settings.get("enabled", False) or args.delta_base)
    previous_path = args.delta_base or delta_settings.get("previous_file")

    if delta_enabled and previous_path:
        previous_items = load_previous_run(previous_path)
        if previous_items:
            all_items = annotate_with_delta(previous_items, all_items)
            logging.info(
                "Delta Mode applied using base file: %s. Total items after delta: %d",
                previous_path,
                len(all_items),
            )
        else:
            logging.warning(
                "Delta Mode requested but previous run data could not be loaded. "
                "Proceeding without delta annotations."
            )
    else:
        logging.info("Delta Mode disabled.")

    # Output
    output_format = args.format or output_settings.get("default_format")
    if not output_format:
        output_format = infer_format_from_output(args.output)

    output_dir = os.path.dirname(args.output) or output_settings.get("output_dir") or "data"
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = os.path.join(os.getcwd(), output_path)

    try:
        export_data(all_items, output_path, output_format)
        logging.info("Export completed: %s (%s)", output_path, output_format)
    except Exception as exc:
        logging.error("Failed to export data to %s: %s", output_path, exc)
        sys.exit(1)

if __name__ == "__main__":
    main()