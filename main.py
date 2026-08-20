import os
import sys
import argparse

import pandas as pd

from utils import load_config
from dotenv import load_dotenv

from brave_crawler import brave_search
from html_fetcher import *
from product_finder import find_product_info

if __name__ == "__main__":
    config = load_config("config.json")
    crawler_cfg = config["crawler"]
    scraper_cfg = config["scraper"]

    parser = argparse.ArgumentParser(description="Search the web using Brave Search API.")
    # Crawler args
    parser.add_argument("query", type=str, help="Search query string.")
    parser.add_argument("--api-key", type=str, help="Brave Search API Key (overrides env variable).")
    parser.add_argument("--count", type=int, help="Total number of results to return (can be > 20).")
    parser.add_argument("--offset", type=int, help="Page offset to start from.")
    parser.add_argument("--country", type=str, help="2-letter country code (e.g. GR, US).")
    parser.add_argument("--search_lang", type=str, help="Language code (e.g. el, en).")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format.")
    # Scraper args
    parser.add_argument("--cffi", action="store_true", help="Use curl_cffi request module.")
    parser.add_argument("--verbose", action="store_true", help="Display messages during the process.")

    flatten_configs = {**crawler_cfg, **scraper_cfg}
    parser.set_defaults(**flatten_configs)
    args = parser.parse_args()

    # Call brave search to find e-shops selling the specified product (the query string)
    # Set your Brave Search API key here or via the BRAVE_API_KEY environment variable.
    load_dotenv()
    BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
    search_results = brave_search(
        query=args.query,
        api_key=args.api_key or BRAVE_API_KEY,
        count=args.count,
        offset=args.offset,
        country=args.country,
        search_lang=args.search_lang,
    )

    if not search_results:
        sys.exit(1)

    # Gather all the URLs
    urls = [result['url'] for result in search_results] # this works for both txt and json

    if args.cffi:
        print("\n*** Using curl_cffi requests ***")

    products_data = []

    for url in urls:
        print(f"\nLooking at {get_domain(url)}")
        
        html_soup = get_html(url, headers=args.headers, use_cffi=args.cffi)

        # Make sure HTML was retrieved successfully
        if not html_soup:
            continue

        product_info = find_product_info(html_soup)

        if not product_info:
            continue

        # Add the source url and the domain of the page
        product_info["source_url"] = url
        product_info["source_domain"] = get_domain(url)

        products_data.append(product_info)

    # Output result into a file
    df = pd.DataFrame(products_data)
    df.to_excel("main_out.xlsx", header=True, index=True)