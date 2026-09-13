from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import BrowserContext, Page, sync_playwright

LOGGER = logging.getLogger(__name__)

LOGIN_URL = "https://pro.galim.org.il/login"
LMS_PERSONAL_URL = "https://lms.galim.org.il/personal"
LMS_ORIGIN = "https://lms.galim.org.il"


class GalimAuthenticationError(RuntimeError):
    """Raised when Galim authentication does not produce an LMS session."""


class GalimAuthenticator:
    def __init__(
        self,
        username: str,
        password: str,
        *,
        storage_state_path: Path,
        headless: bool = True,
    ) -> None:
        self.username = username
        self.password = password
        self.storage_state_path = Path(storage_state_path)
        self.headless = headless

    @staticmethod
    def _sid(context: BrowserContext) -> str | None:
        for cookie in context.cookies(LMS_ORIGIN):
            if cookie.get("name") == "SID" and cookie.get("value"):
                return str(cookie["value"])
        return None

    def _open_context(self, browser) -> BrowserContext:
        if self.storage_state_path.exists():
            try:
                return browser.new_context(storage_state=str(self.storage_state_path))
            except Exception as exc:
                LOGGER.warning("Stored browser session could not be loaded: %s", exc)
        return browser.new_context()

    def _save(self, context: BrowserContext) -> None:
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(self.storage_state_path))
        self.storage_state_path.chmod(0o600)

    @staticmethod
    def _synchronize_lms(page: Page) -> None:
        page.goto(LMS_PERSONAL_URL, wait_until="networkidle", timeout=60_000)

    @staticmethod
    def _safe_page_location(page: Page) -> str:
        """Describe a failed page without logging query strings or fragments."""
        try:
            parsed = urlsplit(page.url)
            location = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            title = page.title().strip()[:100]
            return f"{location} (title={title!r})"
        except Exception:
            return "unavailable"

    def login(self) -> str:
        """Return a valid LMS SID, reusing browser state before interactive login."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            context = self._open_context(browser)
            page = context.new_page()
            try:
                if self.storage_state_path.exists():
                    LOGGER.info("Trying the persisted Galim browser session")
                    self._synchronize_lms(page)
                    sid = self._sid(context)
                    if sid:
                        self._save(context)
                        return sid

                LOGGER.info("Authenticating with Galim Pro")
                page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
                page.get_by_text("הזדהות משרד החינוך", exact=False).click(timeout=20_000)
                page.wait_for_selector("#userName", timeout=30_000)
                page.fill("#userName", self.username)
                page.click("#password")
                page.fill("#password", self.password)
                page.locator("button#submit, input[type='submit'], button[type='submit']").first.click()
                page.wait_for_url("**/student**", timeout=60_000)
                self._synchronize_lms(page)

                sid = self._sid(context)
                if not sid:
                    raise GalimAuthenticationError("Login completed without an LMS SID cookie")
                self._save(context)
                return sid
            except GalimAuthenticationError:
                raise
            except Exception as exc:
                location = self._safe_page_location(page)
                raise GalimAuthenticationError(
                    f"Galim login failed at {location}: {exc}"
                ) from exc
            finally:
                context.close()
                browser.close()

    def clear_saved_session(self) -> None:
        if self.storage_state_path.exists():
            self.storage_state_path.unlink()
