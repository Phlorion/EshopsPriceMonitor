import os
import sys
import argparse

import pandas as pd

from utils import load_config, ensure_dir
from dotenv import load_dotenv

from brave_crawler import brave_search
from html_fetcher import *
from product_finder import find_product_info


async def scrape_data_main(args, urls):
    if args.cffi:
        print("\n*** Using curl_cffi requests ***")

    semaphore = asyncio.Semaphore(10)

    async def _process_url(url):
        html_soup = await get_html(url, semaphore=semaphore, headers=args.headers, use_cffi=args.cffi)

        # Make sure HTML was retrieved successfully
        if not html_soup:
            return None

        product_info = find_product_info(html_soup, url, args.verbose)

        if not product_info:
            return None

        # Add the source url and the domain of the page
        product_info["source_url"] = url
        product_info["source_domain"] = get_domain(url)

        return product_info

    print(f"\nLaunching {len(urls)} scraping tasks...\n")
    tasks = [_process_url(url) for url in urls]

    results = await asyncio.gather(*tasks)
    return [result for result in results if result is not None]


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
    # Scraper args
    parser.add_argument("--cffi", action="store_true", help="Use curl_cffi request module.")
    parser.add_argument("--verbose", action="store_true", help="Display messages during the process.")
    parser.add_argument("--json", action="store_true", help="Output JSON format.")

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

    # Load skiplist to remove unwanted domains
    with open("skiplist.txt", "r") as f:
        skiplist = [line[:-1] for line in f.readlines()]

    # Gather all the URLs and remove domains that exist in the skiplist
    urls = [result['url'] for result in search_results if get_domain(result['url']) not in skiplist]

    # Get the data
    products_data = asyncio.run(scrape_data_main(args, urls))

    # Output result into a file
    df = pd.DataFrame(products_data)

    ensure_dir("out") # Make sure the out directory exists
    if args.json:
        df.to_json("out/main_out.json", indent=2, force_ascii=False, orient="records")
    else:
        df.to_excel("out/main_out.xlsx", header=True, index=True)