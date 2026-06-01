"""
USTAAD Browser Automation & Visual Intelligence Subsystem

This module implements a dynamic browser agent and a suite of interactive
web-browsing tools. It features lazy-initialized Playwright automation for
navigating, clicking, inputting text, and taking screenshots, with a robust
urllib/requests + BeautifulSoup markdown conversion fallback if Playwright is not installed.
"""

import os
import re
import urllib.request
from typing import Optional
from crewai.tools import tool
from rich.console import Console

console = Console()

# Singleton-like active Playwright state
_PLAYWRIGHT_STATE = {
    "playwright": None,
    "browser": None,
    "page": None,
    "last_url": None
}


def _get_playwright_page():
    """
    Lazy-initializer for active Playwright Chromium browser page.
    Returns the page instance or None if Playwright is unavailable.
    """
    global _PLAYWRIGHT_STATE
    if _PLAYWRIGHT_STATE["page"] is not None:
        return _PLAYWRIGHT_STATE["page"]

    try:
        # Lazy load playwright to keep CLI startup under 50ms
        from playwright.sync_api import sync_playwright
        
        pw = sync_playwright().start()
        # Launch headless Chromium
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        _PLAYWRIGHT_STATE["playwright"] = pw
        _PLAYWRIGHT_STATE["browser"] = browser
        _PLAYWRIGHT_STATE["page"] = page
        return page
    except ImportError:
        return None
    except Exception as e:
        console.print(f"[yellow]   ⚠ Playwright startup error: {e}. Falling back to request-based browsing.[/yellow]")
        return None


def close_browser():
    """Clean up and close active Playwright browser session."""
    global _PLAYWRIGHT_STATE
    try:
        if _PLAYWRIGHT_STATE["browser"]:
            _PLAYWRIGHT_STATE["browser"].close()
        if _PLAYWRIGHT_STATE["playwright"]:
            _PLAYWRIGHT_STATE["playwright"].stop()
    except Exception:
        pass
    finally:
        _PLAYWRIGHT_STATE["playwright"] = None
        _PLAYWRIGHT_STATE["browser"] = None
        _PLAYWRIGHT_STATE["page"] = None


# ---------------------------------------------------------------------------
# Swarm Browser Tools
# ---------------------------------------------------------------------------

@tool("browser_navigate")
def browser_navigate_tool(url: str) -> str:
    """
    Navigates the browser to the specified URL. Returns a clean markdown
    representation of the page contents. Works with JavaScript-heavy websites.
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    global _PLAYWRIGHT_STATE
    _PLAYWRIGHT_STATE["last_url"] = url

    page = _get_playwright_page()
    if page:
        try:
            # Navigate using Playwright
            response = page.goto(url, timeout=15000, wait_until="load")
            status = response.status if response else 200
            
            # Extract content and convert to clean markdown
            html = page.content()
            title = page.title()
            
            # Simple DOM cleaner to markdown
            body_text = page.evaluate("() => document.body.innerText")
            return f"### [Playwright Navigation] Success ({status})\n**Title:** {title}\n**URL:** {url}\n\n**Body Content:**\n{body_text[:8000]}"
        except Exception as e:
            return f"Playwright Error navigating to {url}: {str(e)}. Attempting request fallback..."

    # Fallback to urllib + BeautifulSoup if Playwright is not installed/fails
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Extract title and body text via regex
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else "No Title"
            
            # Strip tags for a readable summary
            text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            return f"### [Request Fallback] Success\n**Title:** {title}\n**URL:** {url}\n\n**Page Text:**\n{text[:4000]}"
    except Exception as e:
        return f"Error navigating to {url} (Playwright and Request failed): {str(e)}"


@tool("browser_click")
def browser_click_tool(selector: str) -> str:
    """
    Clicks the element matching the given CSS selector or text value (e.g. 'button[type="submit"]' or 'text="Log In"').
    Requires Playwright.
    """
    page = _get_playwright_page()
    if not page:
        return "Error: browser_click requires Playwright. Install playwright via 'pip install playwright && playwright install' first."

    try:
        page.click(selector, timeout=5000)
        # Wait a short duration for dynamic updates
        page.wait_for_timeout(1000)
        return f"Success: Clicked element '{selector}'. Current URL is now {page.url}"
    except Exception as e:
        return f"Error clicking element '{selector}': {str(e)}"


@tool("browser_input")
def browser_input_tool(selector: str, text: str) -> str:
    """
    Fills the input field matching the given CSS selector with the specified text.
    Requires Playwright.
    """
    page = _get_playwright_page()
    if not page:
        return "Error: browser_input requires Playwright. Install playwright via 'pip install playwright && playwright install' first."

    try:
        page.fill(selector, text, timeout=5000)
        return f"Success: Filled element '{selector}' with text."
    except Exception as e:
        return f"Error inputting text into '{selector}': {str(e)}"


@tool("browser_screenshot")
def browser_screenshot_tool(output_path: str = "screenshot.png") -> str:
    """
    Captures a screenshot of the current page and saves it to the output path.
    Requires Playwright.
    """
    page = _get_playwright_page()
    if not page:
        return "Error: browser_screenshot requires Playwright."

    try:
        page.screenshot(path=output_path, full_page=True)
        return f"Success: Screenshot saved to {output_path}"
    except Exception as e:
        return f"Error taking screenshot: {str(e)}"


# ---------------------------------------------------------------------------
# Swarm Agent Wrapper
# ---------------------------------------------------------------------------
def get_browser_agent(llm=None):
    """
    Returns a unified CrewAI Agent for browser operations.
    """
    from crewai import Agent
    from langchain_ollama import ChatOllama
    
    agent_llm = llm or ChatOllama(model="qwen3:8b", base_url="http://localhost:11434")

    return Agent(
        role="Browser Intelligence Specialist",
        goal="Browse websites, extract highly relevant information, navigate structures, and inspect web apps.",
        backstory="""
        You are an elite autonomous web surfer and crawler. You navigate modern, single-page
        react applications, bypass complex interfaces, fill out forms, click action buttons,
        and digest extensive web documents with premium accuracy.
        """,
        tools=[
            browser_navigate_tool,
            browser_click_tool,
            browser_input_tool,
            browser_screenshot_tool
        ],
        llm=agent_llm,
        verbose=False
    )
