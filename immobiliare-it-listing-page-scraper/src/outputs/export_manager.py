thonimport csv
import json
import logging
import os
from html import escape
from typing import Any, Dict, List

def _ensure_directory(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

def _export_json(items: List[Dict[str, Any]], path: str) -> None:
    _ensure_directory(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    logging.debug("JSON export completed: %s", path)

def _export_csv(items: List[Dict[str, Any]], path: str) -> None:
    _ensure_directory(path)
    if not items:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("")  # create empty file
        logging.debug("CSV export completed (empty dataset): %s", path)
        return

    # Determine union of keys
    keys = set()
    for item in items:
        keys.update(item.keys())
    fieldnames = sorted(keys)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            row: Dict[str, Any] = {}
            for k in fieldnames:
                v = item.get(k)
                if isinstance(v, list):
                    v = " | ".join(str(x) for x in v)
                row[k] = v
            writer.writerow(row)
    logging.debug("CSV export completed: %s", path)

def _export_html(items: List[Dict[str, Any]], path: str) -> None:
    _ensure_directory(path)
    if not items:
        html = "<html><head><meta charset='utf-8'><title>Listings</title></head><body><p>No data.</p></body></html>"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        logging.debug("HTML export completed (empty dataset): %s", path)
        return

    keys = set()
    for item in items:
        keys.update(item.keys())
    fieldnames = sorted(keys)

    rows = []
    for item in items:
        tds = []
        for k in fieldnames:
            v = item.get(k)
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v)
            if v is None:
                v = ""
            tds.append(f"<td>{escape(str(v))}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")

    header_cells = "".join(f"<th>{escape(k)}</th>" for k in fieldnames)
    table_html = (
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<thead><tr>"
        + header_cells
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )

    html = (
        "<html><head><meta charset='utf-8'><title>Listings</title></head>"
        "<body><h1>Immobiliare.it Listings</h1>"
        + table_html
        + "</body></html>"
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    logging.debug("HTML export completed: %s", path)

def export_data(items: List[Dict[str, Any]], path: str, fmt: str) -> None:
    fmt = fmt.lower()
    logging.info("Exporting %d items to %s (%s)", len(items), path, fmt)
    if fmt == "json":
        _export_json(items, path)
    elif fmt == "csv":
        _export_csv(items, path)
    elif fmt == "html":
        _export_html(items, path)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")