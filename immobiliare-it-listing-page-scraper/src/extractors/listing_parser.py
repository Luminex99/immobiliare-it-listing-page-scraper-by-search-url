thonimport logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

import requests
from bs4 import BeautifulSoup

from utils.data_cleaner import (
    clean_text,
    parse_price,
    parse_int,
    parse_float,
)

def build_page_url(base_url: str, page: int) -> str:
    """
    Build a paginated URL for Immobiliare.it search results.

    Immobiliare typically uses ?pag=2 or &pag=2.
    This helper is defensive and works with most standard query patterns.
    """
    if page <= 1:
        return base_url

    parsed = urlparse(base_url)
    query = parse_qs(parsed.query)
    query["pag"] = [str(page)]
    new_query = urlencode({k: v[0] if isinstance(v, list) else v for k, v in query.items()})
    paginated = parsed._replace(query=new_query)
    return urlunparse(paginated)

def create_http_session(user_agent: Optional[str] = None, timeout: int = 20) -> requests.Session:
    session = requests.Session()
    headers = {
        "User-Agent": user_agent
        or "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/123.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    }
    session.headers.update(headers)
    session.timeout = timeout  # type: ignore[attr-defined]
    return session

def fetch_page(url: str, session: requests.Session, timeout: int = 20, delay: float = 0.0) -> str:
    if delay > 0:
        time.sleep(delay)
    logging.debug("Fetching URL: %s", url)
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text

def extract_listing_containers(soup: BeautifulSoup) -> List[Any]:
    """
    Try multiple strategies to locate listing cards on Immobiliare.it pages.
    """
    selectors = [
        ("article", {"data-testid": "listing-card"}),
        ("div", {"class": re.compile(r"^nd-list__item")}),
        ("li", {"class": re.compile(r"^nd-list__item")}),
        ("div", {"itemtype": re.compile(r"schema.org/Offer")}),
    ]

    for name, attrs in selectors:
        containers = soup.find_all(name, attrs=attrs)
        if containers:
            logging.debug("Found %d listing containers with selector %s %s", len(containers), name, attrs)
            return containers

    # Fallback to any <article> that looks like a property listing
    fallback = soup.find_all("article")
    logging.debug("Using fallback listing containers: %d article elements.", len(fallback))
    return fallback

def extract_photos(card: Any) -> List[str]:
    urls: List[str] = []
    for img in card.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if src and "immobiliare.it" in src:
            urls.append(src)
    # Deduplicate while preserving order
    seen = set()
    unique_urls: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    return unique_urls

def extract_text(card: Any, selectors: List[Dict[str, Any]]) -> Optional[str]:
    for s in selectors:
        tag = s.get("tag", "div")
        attrs = s.get("attrs", {})
        el = card.find(tag, attrs=attrs)
        if el:
            return clean_text(el.get_text(" ", strip=True))
    return None

def parse_listing_card(card: Any) -> Dict[str, Any]:
    title = extract_text(
        card,
        [
            {"tag": "a", "attrs": {"data-testid": "listing-title"}},
            {"tag": "a", "attrs": {"class": re.compile(r"title")}},
            {"tag": "h2", "attrs": {}},
        ],
    ) or ""

    description = extract_text(
        card,
        [
            {"tag": "p", "attrs": {"data-testid": "listing-description"}},
            {"tag": "p", "attrs": {"class": re.compile(r"description")}},
        ],
    ) or ""

    location = extract_text(
        card,
        [
            {"tag": "span", "attrs": {"data-testid": "listing-location"}},
            {"tag": "span", "attrs": {"class": re.compile(r"location")}},
        ],
    ) or ""

    price_raw = extract_text(
        card,
        [
            {"tag": "span", "attrs": {"data-testid": "listing-price"}},
            {"tag": "li", "attrs": {"class": re.compile(r"price")}},
        ],
    ) or ""

    surface_raw = None
    surface_el = card.find(string=re.compile(r"m²"))
    if surface_el:
        surface_raw = clean_text(surface_el)

    rooms_raw = None
    rooms_el = card.find(string=re.compile(r"\b(?:locali|stanze|rooms)\b", flags=re.IGNORECASE))
    if rooms_el:
        rooms_raw = clean_text(rooms_el)

    bathrooms_raw = None
    bath_el = card.find(string=re.compile(r"\b(?:bagni|bathrooms?)\b", flags=re.IGNORECASE))
    if bath_el:
        bathrooms_raw = clean_text(bath_el)

    energy_class = None
    energy_el = card.find(string=re.compile(r"Classe", flags=re.IGNORECASE))
    if energy_el:
        energy_class = clean_text(energy_el)

    construction_year = None
    year_el = card.find(string=re.compile(r"Anno di costruzione|Costruito nel", flags=re.IGNORECASE))
    if year_el:
        construction_year = parse_int(year_el)

    agency_name = extract_text(
        card,
        [
            {"tag": "span", "attrs": {"data-testid": "listing-agency-name"}},
            {"tag": "div", "attrs": {"class": re.compile(r"agency")}},
        ],
    )

    contact_info = None
    phone_el = card.find(string=re.compile(r"\+?\d{6,}", flags=re.IGNORECASE))
    if phone_el:
        contact_info = clean_text(phone_el)

    transport = None
    transport_el = card.find(string=re.compile(r"(metro|bus|tram|fermata)", flags=re.IGNORECASE))
    if transport_el:
        transport = clean_text(transport_el)

    listing: Dict[str, Any] = {
        "title": title,
        "description": description,
        "price": price_raw,
        "price_value": parse_price(price_raw),
        "location": location,
        "surface": surface_raw,
        "surface_value_m2": parse_float(surface_raw) if surface_raw else None,
        "rooms": parse_int(rooms_raw),
        "bathrooms": parse_int(bathrooms_raw),
        "photos": extract_photos(card),
        "energy_class": energy_class,
        "construction_year": construction_year,
        "agency_name": agency_name,
        "contact_info": contact_info,
        "transport": transport,
        # Set default status; Delta Mode can override
        "apify_monitoring_status": "new",
    }

    return listing

def parse_listings(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    containers = extract_listing_containers(soup)
    listings = [parse_listing_card(card) for card in containers]
    logging.debug("Parsed %d listings from HTML.", len(listings))
    return listings

def scrape_search_url(
    url: str,
    max_pages: Optional[int] = 1,
    user_agent: Optional[str] = None,
    timeout: int = 20,
    parallel_requests: int = 4,
    delay_between_pages: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Scrape an Immobiliare.it search URL for listing data across multiple pages.
    """
    session = create_http_session(user_agent=user_agent, timeout=timeout)

    if max_pages is None or max_pages < 1:
        max_pages = 1

    page_urls = [build_page_url(url, page) for page in range(1, max_pages + 1)]

    listings: List[Dict[str, Any]] = []

    def fetch_and_parse(page_url: str, page_index: int) -> List[Dict[str, Any]]:
        try:
            html = fetch_page(page_url, session=session, timeout=timeout, delay=delay_between_pages * page_index)
            page_listings = parse_listings(html)
            logging.info("Page %d: %d listings found.", page_index, len(page_listings))
            return page_listings
        except Exception as exc:
            logging.error("Failed to fetch or parse page %s: %s", page_url, exc)
            return []

    if parallel_requests <= 1 or len(page_urls) == 1:
        for i, page_url in enumerate(page_urls, start=1):
            listings.extend(fetch_and_parse(page_url, i))
    else:
        with ThreadPoolExecutor(max_workers=parallel_requests) as executor:
            future_to_page = {
                executor.submit(fetch_and_parse, page_url, i): i
                for i, page_url in enumerate(page_urls, start=1)
            }
            for future in as_completed(future_to_page):
                page_index = future_to_page[future]
                try:
                    page_listings = future.result()
                    listings.extend(page_listings)
                except Exception as exc:
                    logging.error("Error processing page %d: %s", page_index, exc)

    logging.info("Total listings scraped for URL %s: %d", url, len(listings))
    return listings