import json
import re
import html
from bs4 import BeautifulSoup
from product_extractor import *
import os
import argparse
from html_fetcher import get_html
from utils import load_config


def find_product_info(soup: BeautifulSoup, verbose: bool = False):
    """Finds the application/ld+json scripts and looks for the Product information.
    If the Product JSON is found, extracts crucial data such as item name, barcode, price and availability.

    Args:
    soup (BeautifulSoup): The full BeautifulSoup object of the page's HTML.
    verbose (bool, optional): Display messages in detail.
    """
    
    # Grab every JSON-LD in the page
    json_scripts = soup.find_all("script", type="application/ld+json")
    if verbose and len(json_scripts) == 0:
        print("[!] Found 0 'application/ld+json' scripts.")

    for idx, script in enumerate(json_scripts, 1):
        # Extract raw text for each script
        raw_text = script.get_text(strip=True)

        if not raw_text:
            continue

        # Clean CDATA wrappers if present
        raw_text = re.sub(r"^//<!\[CDATA\[|//\]\]>$", "", raw_text).strip()
        raw_text = re.sub(r"^<!\[CDATA\[|\]\]>$", "", raw_text).strip()

        # Unescape HTML entities (e.g. &quot; -> ")
        raw_text = html.unescape(raw_text)

        try:
            # Parse with strict=False to allow unescaped newlines/tabs
            data = json.loads(raw_text, strict=False)

            # Normalization: extract all items, unwrapping any @graph objects or lists
            items = extract_items(data)

            for item in items:
                if not isinstance(item, dict):
                    continue

                item_type = item.get("@type")

                # Check for "Product" (handles string, list, or full schema URI)
                is_product = (
                    (item_type == "Product" or item_type.endswith("/Product"))
                    if isinstance(item_type, str)
                    else (
                        any(
                            t == "Product" or (isinstance(t, str) and t.endswith("/Product"))
                            for t in item_type
                        )
                        if isinstance(item_type, list)
                        else False
                    )
                )

                if is_product:
                    name = item.get("name")
                    barcode = extract_barcode(item)
                    price = extract_price(item)
                    availability = extract_availability(item)

                    print(f"[✓] SUCCESS!")
                    if verbose:
                        print(f"Product Name: {name}")
                        print(f"Barcode: {barcode}")
                        print(f"Price: {price} €")
                        print(f"Availability: {availability}")

                    return {
                        "name": name,
                        "barcode": barcode,
                        "price": price,
                        "availability": availability
                    }

        except json.JSONDecodeError as err:
            if verbose:
                print(f"\n[X] Script #{idx} failed to parse!")
                print(f"Error Message: {err}")
                # Print a snippet around where the error happened
                pos = err.pos
                start = max(0, pos - 40)
                end = min(len(raw_text), pos + 40)
                print(f"Problematic Snippet: ... {raw_text[start:end]} ...")

        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    config = load_config("config.json")
    scraper_cfg = config["scraper"]

    parser = argparse.ArgumentParser(description="Scrape a product's JSON-LD from e-shops.")
    parser.add_argument(
        "target",
        help="A URL address or a filename containing URLs."
    )
    parser.add_argument(
        "--cffi", 
        action="store_true", 
        help="Use curl_cffi request module."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Display messages during the process."
    )

    parser.set_defaults(**scraper_cfg)
    args = parser.parse_args()

    if args.cffi:
        print("\n*** Using curl_cffi requests ***")

    if os.path.isfile(args.target):
        with open(args.target, "r", encoding="utf-8") as file:
            urls = [line.strip() for line in file if line.strip()]
    else:
        urls = [args.target]

    for url in urls:
        print(f"\nLooking at {url}\n")

        html_soup = get_html(url, headers=args.headers, use_cffi=args.cffi)

        if html_soup:
            product_info = find_product_info(html_soup, verbose=args.verbose)
            print(f"\n{json.dumps(product_info, ensure_ascii=False)}")