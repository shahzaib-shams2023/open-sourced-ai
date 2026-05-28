from crewai.tools import tool
import urllib.request
import re

@tool("web_fetcher")
def fetch_url_title(url: str) -> str:
    """
    Fetches a URL and returns its HTML title tag contents.
    Use this to inspect webpage headers and verify online links.
    """
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            if title_match:
                return f"Success: Title of '{url}' is '{title_match.group(1).strip()}'"
            return "Success: Page fetched but no <title> tag found."
    except Exception as e:
        return f"Error fetching URL: {str(e)}"
