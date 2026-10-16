"""Optional browser automation tool with Playwright integration."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import PermissionLevel, SideEffectType
from astra_agent.tools.base import BaseTool

try:
    import playwright
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class BrowserInput(BaseModel):
    """Input parameters for browser automation."""
    url: str = Field(..., description="The HTTP or HTTPS URL to visit.")
    action: str = Field("extract_text", description="Action to perform: 'extract_text', 'title', or 'screenshot'.")
    timeout_seconds: float = Field(20.0, ge=5.0, le=60.0, description="Page navigation timeout.")


class BrowserTool(BaseTool):
    """Automates web page browsing and text extraction using Playwright when available."""

    name = "browser"
    description = "Navigates to a web page and extracts visible text or page metadata."
    permission_level = PermissionLevel.EXTERNAL_NETWORK
    side_effect_type = SideEffectType.NETWORK
    idempotent = True
    default_timeout = 25.0
    input_schema = BrowserInput

    def is_available(self) -> bool:
        return PLAYWRIGHT_AVAILABLE

    def _run(self, inputs: BrowserInput) -> Dict[str, Any]:
        if not self.is_available():
            return {
                "available": False,
                "error": "Playwright is not installed. Install optional browser dependencies via 'pip install playwright && playwright install chromium'.",
                "url": inputs.url,
            }

        # Validate URL scheme to prevent file:// or internal scheme SSRF
        if not inputs.url.startswith(("http://", "https://")):
            raise ValueError("Browser only supports 'http://' and 'https://' URLs.")

        # Disallow loopback / private IP SSRF if external network is constrained
        disallowed_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"]
        if any(host in inputs.url.lower() for host in disallowed_hosts):
            raise ValueError("Access to local or cloud metadata endpoints is prohibited.")

        async def _navigate_and_extract() -> Dict[str, Any]:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                try:
                    await page.goto(inputs.url, timeout=int(inputs.timeout_seconds * 1000))
                    title = await page.title()
                    
                    if inputs.action == "title":
                        content = title
                    else:
                        # Extract clean text from body
                        content = await page.inner_text("body")
                        # Truncate content to avoid token explosions
                        content = content[:4000]

                    return {
                        "available": True,
                        "url": inputs.url,
                        "title": title,
                        "content": content,
                        "action": inputs.action,
                    }
                finally:
                    await browser.close()

        # Run async coroutine safely in synchronous tool execution
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In nested event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(_navigate_and_extract())).result()
            else:
                return loop.run_until_complete(_navigate_and_extract())
        except Exception as e:
            return {
                "available": True,
                "url": inputs.url,
                "error": f"Browser navigation failed: {str(e)}",
            }
