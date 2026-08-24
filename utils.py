import json
import os
import sys
from pathlib import Path


# The browser will run this JavaScript in a loop until it returns `true`
wait_js = """
() => {
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (let script of scripts) {
        try {
            const data = JSON.parse(script.innerText);
            // JSON-LD can be a dictionary or a list of dictionaries
            const items = Array.isArray(data) ? data : [data];
            
            for (let item of items) {
                // Check if the exact Schema type is Product
                if (item['@type'] === 'Product' || 
                   (Array.isArray(item['@type']) && item['@type'].includes('Product'))) {
                    return true;
                }
            }
        } catch (e) {
            // Ignore JSON parsing errors while the script is still downloading
            continue;
        }
    }
    return false; // Keep waiting
}
"""


def load_config(file_path: str = "config.json") -> dict:
    """Reads the JSON configuration file."""
    if not os.path.exists(file_path):
        print(f"[!] Warning: Config file '{file_path}' not found. Using script defaults.")
        return {"crawler": {}, "scraper": {}}
    
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return {
                "crawler": data.get("crawler", {}),
                "scraper": data.get("scraper", {})
            }
        except json.JSONDecodeError:
            print("[X] Error: Invalid JSON format in config file.")
            sys.exit(1)


def ensure_dir(dir_path: str):
    """
    Checks if a directory exists and creates it if it doesn't.
    """
    Path(dir_path).mkdir(parents=True, exist_ok=True)