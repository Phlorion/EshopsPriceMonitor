import re


def extract_items(obj: dict) -> list:
    """Recursively extract all JSON-LD items, unwrapping any '@graph' objects or lists.
    Useful to iterate through the items and locate the Product item.

    Args:
    obj (dict): JSON object of the full application/ld+json script.

    Returns:
    A list with all the items inside the JSON object.
    """
    extracted = []
    if isinstance(obj, list):
        for elem in obj:
            extracted.extend(extract_items(elem))
    elif isinstance(obj, dict):
        if "@graph" in obj:
            extracted.extend(extract_items(obj["@graph"]))
        extracted.append(obj)
    return extracted


def extract_barcode(item_dict: dict) -> str:
    """Smart helper that extracts a 13-digit EAN barcode from a Product schema.

    Checks:
    1. Direct candidate keys (gtin13, gtin, sku, mpn, productID, identifier, barcode, etc.).
    2. Embedded 13-digit numbers within SKU/MPN strings (e.g. 'SKU-5201234567890').
    3. Image URLs (e-commerce sites frequently name image files after the barcode, e.g. '5201234567890.jpg').
    4. Keyword patterns (e.g. 'Barcode: 5201234567890') in description/text fields.
    5. Recursive search across all nested strings for any 13-digit sequence.
    6. Fallback to raw SKU or MPN value if no 13-digit EAN barcode is found.

    Args:
    item_dict (dict): The JSON containing the Product information inside the application/ld+json script.

    Returns:
    A string of the Product's barcode. None if the provided item_dict is not of type dict or no barcode is found.
    """
    if not isinstance(item_dict, dict):
        return None

    # Step 1: Candidate keys in order of preference
    candidate_keys = [
        "gtin13",
        "gtin",
        "gtin14",
        "gtin8",
        "sku",
        "mpn",
        "productID",
        "barcode",
        "Barcode",
        "EAN",
        "ean",
        "identifier",
    ]

    # Check candidate keys for a 13-digit EAN sequence
    for key in candidate_keys:
        val = item_dict.get(key)
        if val and isinstance(val, (str, int)):
            val_str = str(val).strip()
            match = re.search(r"(?<!\d)(\d{13})(?!\d)", val_str)
            if match:
                return match.group(1)

    def _collect_strings(obj):
        """Helper to recursively collect all strings from a dict or list structure."""
        strings = []
        if isinstance(obj, str):
            strings.append(obj)
        elif isinstance(obj, list):
            for elem in obj:
                strings.extend(_collect_strings(elem))
        elif isinstance(obj, dict):
            for v in obj.values():
                strings.extend(_collect_strings(v))
        return strings

    # Step 2: Check image URLs (e-commerce platforms often use barcode in image filenames)
    images = item_dict.get("image")
    if images:
        for img_url in _collect_strings(images):
            match = re.search(r"(?<!\d)(\d{13})(?!\d)", img_url)
            if match:
                return match.group(1)

    # Step 3: Search for explicit keywords like "Barcode: 5201234567890" across all nested strings
    all_strings = _collect_strings(item_dict)
    keyword_regex = re.compile(r"(?i)(?:barcode|bar code|ean|gtin)[\s\:\-]+(\d{13})")
    for text in all_strings:
        match = keyword_regex.search(text)
        if match:
            return match.group(1)

    # Step 4: Search all nested string values for any standalone 13-digit number
    for text in all_strings:
        match = re.search(r"(?<!\d)(\d{13})(?!\d)", text)
        if match:
            return match.group(1)

    # Step 5: Fallback to raw SKU / MPN string even if not 13 digits
    for key in ["sku", "mpn", "gtin13", "gtin"]:
        val = item_dict.get(key)
        if val and isinstance(val, (str, int)):
            return str(val).strip()

    return None


def extract_price(item_dict) -> str | float:
    """Smart helper that extracts product price from a JSON-LD structure.

    Checks:
    1. Direct 'offers' object (Offer, AggregateOffer, list of offers, etc.).
    2. Direct price keys on Product ('price', 'lowPrice', 'highPrice', 'minPrice', 'maxPrice', etc.).
    3. Nested 'priceSpecification' objects (UnitPriceSpecification, CompoundPriceSpecification).
    4. Nested 'offers' inside AggregateOffer or offer catalogs.
    5. Product variants ('hasVariant', 'variant', 'itemListElement', 'model').
    6. General recursive search across nested structures for any valid price.
    7. Cleans and parses string prices (e.g. '19,99 €', '€1,234.56', '19.99 EUR').

    Args:
    item_dict (dict): The JSON containing the Product information inside the application/ld+json script.

    Returns:
    The Product's price. None if the provided item_dict is not of type dict or no price is found.

    """
    if not isinstance(item_dict, dict):
        return None

    price_keys = [
        "price",
        "lowPrice",
        "highPrice",
        "minPrice",
        "maxPrice",
        "Price",
        "lowprice",
        "highprice",
        "priceAmount",
    ]

    def _parse_price(val):
        """Helper to extract a float/int price from numbers or formatted strings."""
        if val is None or val == "":
            return None
        if isinstance(val, (int, float)):
            return val
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return None
            try:
                return float(s)
            except ValueError:
                pass

            # Standardize thousand separators and decimal points
            if "." in s and "," in s:
                if s.rfind(",") > s.rfind("."):
                    s = s.replace(".", "").replace(",", ".")
                else:
                    s = s.replace(",", "")
            elif "," in s:
                parts = s.split(",")
                if len(parts) == 2 and len(parts[1].strip().split()[0]) <= 2:
                    s = s.replace(",", ".")
                else:
                    s = s.replace(",", "")

            match = re.search(r"\d+(?:\.\d+)?", s)
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    pass
        return None

    def _get_price_from_dict(d):
        if not isinstance(d, dict):
            return None

        # Check candidate keys in dict
        for key in price_keys:
            if key in d:
                parsed = _parse_price(d[key])
                if parsed is not None:
                    return parsed

        # Check priceSpecification in dict
        price_spec = d.get("priceSpecification")
        if price_spec:
            specs = price_spec if isinstance(price_spec, list) else [price_spec]
            for spec in specs:
                if isinstance(spec, dict):
                    for spec_key in price_keys + ["value"]:
                        if spec_key in spec:
                            parsed = _parse_price(spec[spec_key])
                            if parsed is not None:
                                return parsed
        return None

    # Step 1: Check 'offers' explicitly (dict or list)
    offers = item_dict.get("offers")
    if offers:
        offers_list = offers if isinstance(offers, list) else [offers]
        for offer in offers_list:
            if isinstance(offer, dict):
                p = _get_price_from_dict(offer)
                if p is not None:
                    return p
                # Check nested offers within AggregateOffer or OfferCatalog
                nested_offers = offer.get("offers") or offer.get("itemListElement")
                if nested_offers:
                    sub_list = nested_offers if isinstance(nested_offers, list) else [nested_offers]
                    for sub in sub_list:
                        if isinstance(sub, dict):
                            p = _get_price_from_dict(sub)
                            if p is not None:
                                return p

    # Step 2: Check direct price keys on top-level item dict
    p = _get_price_from_dict(item_dict)
    if p is not None:
        return p

    # Step 3: Check variants ('hasVariant', 'variant', 'itemListElement', 'model')
    for variant_key in ["hasVariant", "variant", "itemListElement", "model"]:
        variants = item_dict.get(variant_key)
        if variants:
            v_list = variants if isinstance(variants, list) else [variants]
            for v in v_list:
                if isinstance(v, dict):
                    p = extract_price(v)
                    if p is not None:
                        return p

    # Step 4: General recursive search fallback across all nested structures
    def _search_recursive(obj, visited=None):
        if visited is None:
            visited = set()

        obj_id = id(obj)
        if obj_id in visited:
            return None
        visited.add(obj_id)

        if isinstance(obj, dict):
            p = _get_price_from_dict(obj)
            if p is not None:
                return p
            for k, v in obj.items():
                if k not in ("@context", "image", "description"):
                    p = _search_recursive(v, visited)
                    if p is not None:
                        return p
        elif isinstance(obj, list):
            for elem in obj:
                p = _search_recursive(elem, visited)
                if p is not None:
                    return p
        return None

    for k, v in item_dict.items():
        if k not in ("offers", "hasVariant", "variant", "itemListElement", "model", "@context", "image", "description"):
            p = _search_recursive(v)
            if p is not None:
                return p

    return None


def extract_availability(item_dict: dict) -> str:
    """Smart helper that extracts availability status from JSON-LD structure.

    Args:
    item_dict (dict): The JSON containing the Product information inside the application/ld+json script.

    Returns:
    The Product's availability.
    """
    if not isinstance(item_dict, dict):
        return "Unknown"

    def _clean_availability(raw):
        if not raw:
            return None
        val_str = str(raw)
        return val_str.split("/")[-1]

    # Check offers
    offers = item_dict.get("offers")
    if offers:
        offers_list = offers if isinstance(offers, list) else [offers]
        for offer in offers_list:
            if isinstance(offer, dict):
                avail = _clean_availability(offer.get("availability"))
                if avail:
                    return avail
                nested = offer.get("offers") or offer.get("itemListElement")
                if nested:
                    sub_list = nested if isinstance(nested, list) else [nested]
                    for sub in sub_list:
                        if isinstance(sub, dict):
                            avail = _clean_availability(sub.get("availability"))
                            if avail:
                                return avail

    # Check direct availability
    raw_direct = item_dict.get("availability")
    if raw_direct:
        return _clean_availability(raw_direct)

    return "Unknown"