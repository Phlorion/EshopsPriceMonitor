import os
import sys
import argparse
import json
import requests
from utils import load_config
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def brave_search(
    query: str,
    api_key: Optional[str] = None,
    count: int = 10,
    offset: int = 0,
    country: Optional[str] = None,
    search_lang: Optional[str] = None,
    safesearch: str = "moderate",
    extra_params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Performs a web search using the Brave Search API with automatic pagination.

    Brave Search API returns up to 20 results per request. If `count` > 20,
    this function will automatically paginate (incrementing `offset`) to fetch
    the requested total number of results (up to maximum allowed offset by API).

    Args:
        query (str): The search query string.
        api_key (str, optional): Brave Search API key. Defaults to environment variable or script constant.
        count (int, optional): Total number of search results to return. Defaults to 10.
        offset (int, optional): Zero-based page offset to start fetching from. Defaults to 0 (max 9).
        country (str, optional): 2-letter country code (e.g., 'GR', 'US').
        search_lang (str, optional): Language code (e.g., 'el', 'en').
        safesearch (str, optional): 'off', 'moderate', or 'strict'. Defaults to 'moderate'.
        extra_params (dict, optional): Additional query parameters for the API.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing search results with keys:
                              'title', 'url', 'description', 'snippet', etc.
    """
    if not api_key:
        raise ValueError(
            "Brave API key not provided. Set the BRAVE_API_KEY environment variable, "
            "pass api_key to brave_search(), or set BRAVE_API_KEY in Brave_Crawler.py by using [--api_key]."
        )

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }

    all_results = []
    current_offset = offset
    remaining = count

    # Brave API max offset is 9 (pages 0-9, up to 200 items max)
    while remaining > 0 and current_offset <= 9:

        params = {
            "q": query,
            "count": 20, # We tell brave to always return its max results in one request which is 20. If we have fewer remaining results, we eliminate the last extra ones.
            "offset": current_offset,
            "safesearch": safesearch,
        }

        if country:
            params["country"] = country
        if search_lang:
            params["search_lang"] = search_lang

        if extra_params:
            params.update(extra_params)

        try:
            response = requests.get(BRAVE_SEARCH_ENDPOINT, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"[X] HTTP Error ({response.status_code}): {http_err}", file=sys.stderr)
            break
        except requests.exceptions.RequestException as req_err:
            print(f"[X] Request failed: {req_err}", file=sys.stderr)
            break
        except json.JSONDecodeError as json_err:
            print(f"[X] Failed to parse JSON response: {json_err}", file=sys.stderr)
            break

        # Extract web search results
        web_data = data.get("web", {})
        results = web_data.get("results", [])

        if not results:
            # No more results available
            break

        # If the API gave us more results than we still need, chop off the excess
        if len(results) > remaining:
            results = results[:remaining]

        for item in results:
            all_results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
                "extra_snippets": item.get("extra_snippets", []),
                "page_age": item.get("page_age"),
                "profile": item.get("profile", {}),
            })

        remaining -= len(results)
        current_offset += 1

    return all_results


def get_search_urls(query: str, api_key: Optional[str] = None, count: int = 10, offset: int = 0) -> List[str]:
    """Helper function that returns only a list of result URLs for a given query."""
    results = brave_search(query=query, api_key=api_key, count=count, offset=offset)
    return [res["url"] for res in results if "url" in res and res["url"]]


if __name__ == "__main__":
    # Set your Brave Search API key here or via the BRAVE_API_KEY environment variable.
    load_dotenv()
    BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")

    config = load_config("config.json")
    crawler_cfg = config["crawler"]

    parser = argparse.ArgumentParser(description="Search the web using Brave Search API.")
    parser.add_argument("query", type=str, help="Search query string.")
    parser.add_argument("--api-key", type=str, help="Brave Search API Key (overrides env variable).")
    parser.add_argument("--count", type=int, help="Total number of results to return (can be > 20).")
    parser.add_argument("--offset", type=int, help="Page offset to start from.")
    parser.add_argument("--country", type=str, help="2-letter country code (e.g. GR, US).")
    parser.add_argument("--search_lang", type=str, help="Language code (e.g. el, en).")

    parser.set_defaults(**crawler_cfg)
    args = parser.parse_args()

    try:
        search_results = brave_search(
            query=args.query,
            api_key=args.api_key or BRAVE_API_KEY,
            count=args.count,
            offset=args.offset,
            country=args.country,
            search_lang=args.search_lang,
        )

        with open("crawler_out.json", "w") as f:
            f.write(json.dumps(search_results, indent=2, ensure_ascii=False))
        print(f"[✓] {len(search_results)} results for '{args.query}' saved to crawler_out.json.")

    except Exception as e:
        print(f"[X] Error: {e}", file=sys.stderr)
        sys.exit(1)