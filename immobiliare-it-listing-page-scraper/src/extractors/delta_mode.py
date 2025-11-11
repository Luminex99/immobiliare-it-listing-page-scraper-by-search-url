thonimport logging
from typing import Any, Dict, List, Tuple

def _listing_key(item: Dict[str, Any]) -> str:
    """
    Create a stable key for a listing.
    Immobiliare listings usually have unique combinations of title + location + price.
    """
    title = (item.get("title") or "").strip().lower()
    location = (item.get("location") or "").strip().lower()
    price = (item.get("price") or "").strip().lower()
    return f"{title}|{location}|{price}"

def compute_delta(
    previous_items: List[Dict[str, Any]],
    current_items: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Compute which listings are new and which have been delisted between runs.
    Returns:
        (new_items, delisted_items)
    """
    prev_map = {_listing_key(it): it for it in previous_items}
    curr_map = {_listing_key(it): it for it in current_items}

    new_keys = [k for k in curr_map.keys() if k not in prev_map]
    delisted_keys = [k for k in prev_map.keys() if k not in curr_map]

    new_items = [curr_map[k] for k in new_keys]
    delisted_items = [prev_map[k] for k in delisted_keys]

    logging.debug(
        "Delta computation done. New: %d, Delisted: %d", len(new_items), len(delisted_items)
    )
    return new_items, delisted_items

def annotate_with_delta(
    previous_items: List[Dict[str, Any]],
    current_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Annotate listings with `apify_monitoring_status` as 'new' or 'delisted'.
    Current listings which existed previously keep their existing status (if any)
    or have the field removed (they are considered unchanged).
    """
    new_items, delisted_items = compute_delta(previous_items, current_items)

    prev_keys = {_listing_key(it) for it in previous_items}
    curr_keys = {_listing_key(it) for it in current_items}

    # Mark new items
    new_keys = {_listing_key(it) for it in new_items}
    for item in current_items:
        key = _listing_key(item)
        if key in new_keys:
            item["apify_monitoring_status"] = "new"
        else:
            # Existing listing; we keep the field empty to indicate "still active"
            item.pop("apify_monitoring_status", None)

    # For delisted items, clone them and mark as 'delisted'
    annotated_delisted: List[Dict[str, Any]] = []
    for item in delisted_items:
        cloned = dict(item)
        cloned["apify_monitoring_status"] = "delisted"
        annotated_delisted.append(cloned)

    combined = current_items + annotated_delisted

    logging.info(
        "Delta Mode annotation completed. Current: %d, New: %d, Delisted: %d, Combined: %d",
        len(current_items),
        len(new_items),
        len(delisted_items),
        len(combined),
    )

    return combined