import time
import random
import logging
from typing import Dict, Any, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from core.browser_manager import BrowserManager
from core.safety import SafetyManager

logger = logging.getLogger("DMEngine")

class DMEngine:
    """
    Automates Instagram Direct Messaging with human-like interactions,
    multi-strategy element locators, and automated popup dismissal.
    """

    POPUP_DISMISS_SELECTORS = [
        'button:has-text("Not Now")',
        'button:has-text("Cancel")',
        'button:has-text("Decline optional cookies")',
        'button:has-text("Allow essential and optional cookies")',
        'button:has-text("Accept All")',
        'div[role="button"]:has-text("Not Now")',
        'button:has-text("Dismiss")',
        'svg[aria-label="Close"]',
    ]

    def __init__(self, browser_manager: BrowserManager):
        self.browser_manager = browser_manager

    def dismiss_popups(self, page: Page):
        """
        Attempts to click away known intrusive Instagram dialogs (notifications, cookies).
        """
        for sel in self.POPUP_DISMISS_SELECTORS:
            try:
                locator = page.locator(sel)
                if locator.count() > 0 and locator.first.is_visible():
                    locator.first.click(timeout=1500)
                    time.sleep(0.5)
            except Exception:
                pass

    def human_type(self, page: Page, text: str):
        """
        Types text with realistic human speed and micro-delays.
        """
        for char in text:
            page.keyboard.type(char)
            # Vary typing cadence
            if char in " .,!?\n":
                time.sleep(random.uniform(0.12, 0.28))
            else:
                time.sleep(random.uniform(0.04, 0.11))

    def send_dm(self, page: Page, username: str, message: str) -> Dict[str, Any]:
        """
        Sends a direct message to target username using Flow A (Profile)
        with graceful fallback to Flow B (/direct/new/).
        """
        clean_user = username.strip().lstrip("@")
        if not clean_user:
            return {"success": False, "error": "Empty username provided"}

        try:
            self.dismiss_popups(page)

            # --- Flow A: Navigate to User Profile ---
            profile_url = f"https://www.instagram.com/{clean_user}/"
            logger.info(f"Navigating to profile: {profile_url}")
            page.goto(profile_url, wait_until="domcontentloaded", timeout=25000)
            time.sleep(random.uniform(2.0, 3.5))
            self.dismiss_popups(page)

            # 1. Check if profile exists
            body_text = page.inner_text("body")
            if "Sorry, this page isn't available" in body_text or "The link you followed may be broken" in body_text:
                return {"success": False, "error": f"User @{clean_user} not found or account removed"}

            # Check action block
            blocked, block_msg = SafetyManager.is_action_blocked(body_text)
            if blocked:
                self.browser_manager.take_screenshot(page, "action_blocked")
                return {"success": False, "error": block_msg, "action_blocked": True}

            # 2. Locate the "Message" button on profile
            message_btn = None
            candidate_selectors = [
                'div[role="button"]:has-text("Message")',
                'button:has-text("Message")',
                'div:text-is("Message")',
                'header section button:has-text("Message")',
                'header section div[role="button"]:has-text("Message")',
                f'a[href*="/direct/t/"]'
            ]

            for sel in candidate_selectors:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    message_btn = loc.first
                    break

            if message_btn:
                logger.info(f"Clicking Message button on @{clean_user}'s profile")
                message_btn.click()
                time.sleep(random.uniform(2.5, 4.0))
            else:
                # Fallback to Flow B: /direct/new/
                logger.info(f"Message button not found on profile. Attempting /direct/new/ route...")
                return self._send_via_direct_new(page, clean_user, message)

            self.dismiss_popups(page)

            # 3. Locate the conversation message composer
            composer = self._locate_message_input(page)
            if not composer:
                # Last ditch: retry dismiss and check again
                self.dismiss_popups(page)
                composer = self._locate_message_input(page)

            if not composer:
                screenshot = self.browser_manager.take_screenshot(page, f"no_composer_{clean_user}")
                return {
                    "success": False,
                    "error": f"Could not find message input box for @{clean_user} (Account may have DMs disabled)",
                    "screenshot": screenshot
                }

            # 4. Focus, Human Type, and Send
            composer.click()
            time.sleep(random.uniform(0.5, 1.0))
            self.human_type(page, message)
            time.sleep(random.uniform(0.6, 1.2))

            # Send via Enter or clicking Send button
            page.keyboard.press("Enter")
            time.sleep(2.0)

            # Also check if a 'Send' button exists and is enabled
            send_btn = page.locator('div[role="button"]:has-text("Send"), button:has-text("Send")')
            if send_btn.count() > 0 and send_btn.first.is_visible():
                try:
                    send_btn.first.click(timeout=1000)
                    time.sleep(1.5)
                except Exception:
                    pass

            # 5. Check if action block occurred on submit
            page_text = page.inner_text("body")
            blocked, block_msg = SafetyManager.is_action_blocked(page_text)
            if blocked:
                self.browser_manager.take_screenshot(page, "action_blocked_after_send")
                return {"success": False, "error": block_msg, "action_blocked": True}

            logger.info(f"Successfully sent DM to @{clean_user}")
            return {"success": True, "message": f"Sent DM to @{clean_user}"}

        except PlaywrightTimeoutError:
            screenshot = self.browser_manager.take_screenshot(page, f"timeout_{clean_user}")
            return {"success": False, "error": f"Timeout while messaging @{clean_user}", "screenshot": screenshot}
        except Exception as e:
            screenshot = self.browser_manager.take_screenshot(page, f"err_{clean_user}")
            return {"success": False, "error": str(e), "screenshot": screenshot}

    def _locate_message_input(self, page: Page):
        """
        Tries various known selectors for Instagram's DM textbox.
        """
        selectors = [
            'div[contenteditable="true"][role="textbox"]',
            'div[aria-label="Message"]',
            'div[aria-label="Message..."]',
            'div[role="textbox"]',
            'textarea[placeholder*="Message"]',
            'div[contenteditable="true"]',
        ]
        for sel in selectors:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                return loc.first
        return None

    def _send_via_direct_new(self, page: Page, username: str, message: str) -> Dict[str, Any]:
        """
        Fallback path using https://www.instagram.com/direct/new/ search dialog.
        """
        try:
            page.goto("https://www.instagram.com/direct/new/", wait_until="domcontentloaded", timeout=25000)
            time.sleep(2.5)
            self.dismiss_popups(page)

            # Search box for user
            search_input = page.locator('input[name="queryBox"], input[placeholder*="Search"]')
            if search_input.count() == 0:
                return {"success": False, "error": "Search input not found in /direct/new/"}

            search_input.first.click()
            search_input.first.fill(username)
            time.sleep(2.5)

            # Look for user item in results
            user_row = page.locator(f'div[role="button"]:has-text("{username}"), span:text-is("{username}")').first
            if user_row.count() == 0:
                return {"success": False, "error": f"Could not find user @{username} in direct search"}

            user_row.click()
            time.sleep(1.0)

            # Click Chat / Next button
            chat_btn = page.locator('div[role="button"]:has-text("Chat"), button:has-text("Chat"), div[role="button"]:has-text("Next")')
            if chat_btn.count() > 0:
                chat_btn.first.click()
                time.sleep(2.0)

            composer = self._locate_message_input(page)
            if not composer:
                return {"success": False, "error": f"Could not open chat input for @{username}"}

            composer.click()
            self.human_type(page, message)
            time.sleep(0.8)
            page.keyboard.press("Enter")
            time.sleep(2.0)

            return {"success": True, "message": f"Sent DM to @{username} via direct search"}
        except Exception as e:
            return {"success": False, "error": f"Direct/new fallback failed: {str(e)}"}
