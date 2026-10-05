import os
import time
import json
import logging
from typing import Optional, Dict, Any, Tuple
from playwright.sync_api import sync_playwright, BrowserContext, Page, Playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_DIR = os.path.join(BASE_DIR, "browser_profile")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "data", "screenshots")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
window.navigator.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});
"""

class BrowserManager:
    """
    Handles Playwright browser lifecycle with persistent profiles,
    stealth flags, and interactive login sessions.
    """

    def __init__(self, profile_dir: str = PROFILE_DIR, headless: bool = True):
        self.profile_dir = profile_dir
        self.headless = headless
        self._ensure_dirs()
        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None

    def _ensure_dirs(self):
        os.makedirs(self.profile_dir, exist_ok=True)
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    def launch(self, headless: Optional[bool] = None) -> Tuple[BrowserContext, Page]:
        """
        Launches or attaches to the persistent browser context.
        """
        is_headless = self.headless if headless is None else headless

        if self.playwright is None:
            self.playwright = sync_playwright().start()

        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1280,850",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ]

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=is_headless,
            user_agent=DEFAULT_USER_AGENT,
            viewport={"width": 1280, "height": 850},
            args=args,
            color_scheme="dark",
            locale="en-US",
            timezone_id="America/New_York",
            has_touch=False
        )

        # Inject stealth evasions into all new pages
        self.context.add_init_script(STEALTH_SCRIPT)

        page = self.context.pages[0] if self.context.pages else self.context.new_page()
        page.set_default_timeout(25000)
        return self.context, page

    def close(self):
        """
        Safely closes browser context and playwright.
        """
        try:
            if self.context:
                self.context.close()
                self.context = None
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
        except Exception:
            pass

    def check_login_status(self) -> Dict[str, Any]:
        """
        Navigates to Instagram and checks if current session is authenticated.
        """
        try:
            context, page = self.launch(headless=True)
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # Check for common login or logged-in markers
            current_url = page.url
            if "/accounts/login" in current_url:
                self.close()
                return {"logged_in": False, "username": None, "message": "Login page detected"}

            # Look for navigation indicators (Direct messages SVG, profile icon, home icon)
            is_logged_in = False
            username = None

            # Check if any main nav elements exist
            nav_selectors = [
                'svg[aria-label="Direct"]',
                'svg[aria-label="Messages"]',
                'svg[aria-label="Home"]',
                'a[href*="/direct/inbox/"]',
                'div[role="navigation"]'
            ]
            for sel in nav_selectors:
                if page.locator(sel).count() > 0:
                    is_logged_in = True
                    break

            if is_logged_in:
                # Attempt to extract current user handle
                try:
                    profile_link = page.locator('a[href^="/"]:has(img[alt*="profile picture"])').first
                    if profile_link.count() > 0:
                        href = profile_link.get_attribute("href") or ""
                        username = href.strip("/").split("/")[0]
                except Exception:
                    pass

            self.close()
            return {
                "logged_in": is_logged_in,
                "username": username,
                "message": f"Logged in as {username}" if is_logged_in and username else ("Session Active" if is_logged_in else "Not logged in")
            }
        except Exception as e:
            self.close()
            return {"logged_in": False, "username": None, "message": f"Check failed: {str(e)}"}

    def open_interactive_login(self, timeout_seconds: int = 180) -> Dict[str, Any]:
        """
        Launches a visible Chromium window for the user to log in to Instagram.
        Keeps running until user logs in or timeout occurs.
        """
        try:
            self.close()
            context, page = self.launch(headless=False)
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded")

            start_time = time.time()
            logged_in = False
            username = None

            while time.time() - start_time < timeout_seconds:
                try:
                    # Check if page is closed
                    if page.is_closed():
                        break

                    # Check indicators of login
                    url = page.url
                    if "/accounts/login" not in url and url != "https://www.instagram.com/":
                        # Check nav elements
                        nav = page.locator('svg[aria-label="Direct"], svg[aria-label="Messages"], a[href*="/direct/inbox/"]')
                        if nav.count() > 0:
                            logged_in = True
                            break
                    time.sleep(2)
                except Exception:
                    break

            # Attempt to extract username if logged in
            if logged_in:
                try:
                    profile_link = page.locator('a[href^="/"]:has(img[alt*="profile picture"])').first
                    if profile_link.count() > 0:
                        href = profile_link.get_attribute("href") or ""
                        username = href.strip("/").split("/")[0]
                except Exception:
                    pass

            self.close()
            return {
                "success": logged_in,
                "username": username,
                "message": f"Successfully authenticated as {username}" if logged_in and username else ("Logged in successfully!" if logged_in else "Login session ended or timed out.")
            }
        except Exception as e:
            self.close()
            return {"success": False, "error": str(e)}

    def take_screenshot(self, page: Page, name_prefix: str = "error") -> str:
        """
        Saves a debug screenshot into data/screenshots.
        """
        filename = f"{name_prefix}_{int(time.time())}.png"
        filepath = os.path.join(SCREENSHOTS_DIR, filename)
        try:
            page.screenshot(path=filepath, full_page=False)
            return filepath
        except Exception:
            return ""
