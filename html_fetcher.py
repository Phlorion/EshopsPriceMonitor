import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright
from utils import wait_js


def fetch_with_playwright(url: str, **kwargs) -> str:
    """Fetches HTML of a page using playwright. Used to bypass bot detection or load the HTML of CSR webpages if needed.

    Args:
    url (str): The URL of the page we want to scrape.
    headless (bool, optional): Set playwright browser to headless mode. Set to False is recommended to bypass bot detection. Defaults to False.
    window_size (tuple[int, int], optional): The size of the browser window. Defaults to tuple[1080, 720].
    user_agent (str, optional): The user agent of the browser. Defaults to "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36".
    timeout (int, optional): Set timeout in ms when waiting for a response. Defaults to 15000.


    Returns:
    A string with the HTML of the page. None if any error or timeout occurs.
    """

    headless = kwargs.pop("headless", False)
    window_size = kwargs.pop("window_size", (1080, 720))
    user_agent = kwargs.pop("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    timeout = kwargs.pop("timeout", 15000)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        context = browser.new_context(
            user_agent=user_agent,
            viewport={"width": window_size[0], "height": window_size[1]}
        )

        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            page.wait_for_function(wait_js, timeout=timeout) # Inject the JS code inside wait_js that will run in a loop until the Product JSON ld loads.

            return page.content()
        except Exception as err:
            print(f"[X] Load wait finished with notice: {err}")
            return None


def get_html(url: str, **kwargs) -> BeautifulSoup:
    """Fetches HTML of a page using requests.

    Args:
    url (str): The URL of the page we want to scrape.
    headers (dict, optional): The headers sent with the request. Defaults to {}.
    use_cffi (bool, optional): Use curl_cffi requests. Defaults to False.
    impersonate (str, optional): When using curc_cffi choose browser to impersonate. Defauts to chrome.
    timeout (int, optional): Set timeout in seconds when waiting for a response. Defaults to 15.

    Returns:
    A BeautifulSoup object of the page's HTML.
    """

    headers = kwargs.pop("headers", {})
    use_cffi = kwargs.pop("use_cffi", False)
    impersonate = kwargs.pop("impersonate", "chrome")
    timeout = kwargs.pop("timeout", 15)
    try:
        if use_cffi:
            response = cffi_requests.get(url, impersonate=impersonate, timeout=timeout)
        else:
            response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.MissingSchema as err:
        print(f"[X] {err.args[0]}")
        return
    except requests.exceptions.InvalidURL:
        print(f"[X] Invalid URL format: {url}")
        return
    except requests.exceptions.HTTPError as http_err:
        print(f"[X] HTTP Error ({response.status_code}): {http_err}")
        print(f"[!] Fallback to playwright...")
        html = fetch_with_playwright(url)
        if html:
            return BeautifulSoup(html, "html.parser")
        return
    except requests.exceptions.RequestException as req_err:
        # Catches timeouts, connection failures, DNS errors, etc.
        print(f"[X] Request failed: {req_err}")
        return
    except (cffi_requests.errors.RequestsError, cffi_requests.errors.CurlError) as cffi_err:
        print(f"[X] curl_cffi Request failed: {cffi_err}")
        print(f"[!] Fallback to playwright...")
        html = fetch_with_playwright(url)
        if html:
            return BeautifulSoup(html, "html.parser")
        return
    except Exception as general_err:
        # Failsafe for curl_cffi raise_for_status() or other unforeseen errors
        print(f"[X] Unexpected Error: {general_err}")
        return
    
    soup = BeautifulSoup(response.text, "html.parser")
    json_scripts = soup.find_all("script", type="application/ld+json")

    # if no json lds found use playwright as a failsafe
    if len(json_scripts) == 0:
        print("[!] Found 0 'application/ld+json' scripts.")
        print(f"[!] Fallback to playwright...")
        html = fetch_with_playwright(url)
        if html:
            return BeautifulSoup(html, "html.parser")
    else:
        return soup


def get_domain(url: str) -> str:
    """
    Extracts the domain (netloc) from a given URL.
    Handles URLs with or without http/https.

    Args:
    url (str): The URL of the page we want to get the domain.

    Returns:
    The URL's domain name.
    """
    # urlparse requires a scheme (http/https) to correctly identify the domain.
    # If it's missing, we temporarily add it to ensure accurate parsing.
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    parsed_url = urlparse(url)
    domain = parsed_url.netloc

    if not domain.startswith("www."):
        domain = "www." + domain
        
    return domain