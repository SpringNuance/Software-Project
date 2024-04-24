from urllib.parse import urlparse
import tempfile

from ..scrapers.base import *


class PlaywrightScraper(BrowserScraper):
    """Asynchronous scraping using playwright."""

    async def setup(self, playwright) -> None:
        if not self.browser or self.browser == "chrome":
            self.driver_type = playwright.chromium
        else:
            raise Exception("Browser not known/supported.")

        browser_options = {
            "headless": self.headless,
            "args": [],  # chromium options: https://peter.sh/experiments/chromium-command-line-switches/
        }

        context_options = {}

        if self.proxy:
            browser_options["proxy"] = {"server": "per-context"}
            context_options["proxy"] = {"server": self.proxy}

        if self.use_gpu:
            browser_options["args"].append("--enable-gpu")  # --use-gl or --use-angle

        if self.mobile:
            mobile = playwright.devices[self.mobile]
            context_options.update(mobile)

        if self.user_agent:
            context_options["user_agent"] = self.user_agent

        if self.headers:
            context_options["extra_http_headers"] = self.headers

        if self.with_extensions is not None:
            browser_options["args"].extend(
                [
                    f"",
                    f"--disable-extensions-except={self.with_extensions}",
                    f"--load-extension={self.with_extensions}",
                ]
            )
            if self.headless:
                browser_options["args"].append(
                    "--headless=new"
                )  # the new headless arg for chrome v109+. Use '--headless=chrome' as arg for browsers v94-108.

            self.context = await self.driver_type.launch_persistent_context(
                "",
                **{**browser_options, **context_options},
            )
        else:
            self.driver = await self.driver_type.launch(**browser_options)
            self.context = await self.driver.new_context(**context_options)

        if self.timeout is not None:
            self.context.set_default_timeout(self.timeout)

    async def _interceptor(self, route, request):
        # route.request.resource_type could be used here
        # https://playwright.dev/python/docs/api/class-request#request-resource-type
        request_url = urlparse(route.request.url)
        if request_url.path.endswith(self.allow_exts):
            await route.continue_()
        elif request_url.path.endswith(self.block_exts):
            await route.abort()
        await route.continue_()

    def _on_load(self):
        pass

    @staticmethod
    async def _attach_prior_goto(page):
        """Attach custom events to the page prior the navigation."""
        pass

    @staticmethod
    async def _attach_post_goto(page):
        """Attach custom events to the page post the navigation."""
        pass

    async def request_handler(self, request):
        _response = await request.response()
        _cert = await _response.security_details()
        if _response and _response.status == 200:
            response = ResponseOutput(
                body=await _response.body(),
                date=datetime.now(),
                headers=await _response.all_headers(),
                status_code=_response.status,
                reason=_response.status_text,
            )
            _cert = await _response.security_details()
        else:
            response = None
            _cert = {}

        request_url = urlparse(request.url)

        _request = RequestOutput(
            url=request.url,
            body=request.post_data,
            cert=_cert,
            date=datetime.now(),
            headers=await request.all_headers(),
            host=request_url.netloc,
            method=request.method,
            params=request_url.params,
            path=request_url.path,
            response=response,
            resource_type=request.resource_type,
        )
        return _request

    async def scrape(self, url: str, *, headers={}, **kwargs) -> ScraperOutput:
        page = await self.context.new_page()

        await page.route("**", self._interceptor)

        page.once("load", self._on_load)

        _requests = []

        async def request_handler(request):
            try:
                request = await self.request_handler(request)
                _requests.append(request)
            except Exception as e:
                logging.debug(e)

        if self.with_requests:  # process requests if needed
            page.on("requestfinished", request_handler)

        if headers:
            page.set_extra_http_headers(headers=headers)

        if self.implicit_wait:
            await page.wait_for_timeout(self.implicit_wait)

        try:
            await self._attach_prior_goto(page)
            await page.goto(url)
            await self._attach_post_goto(page)
        except Exception as e:
            await page.close()
            raise e

        _body = await page.content()
        _body = bytes(_body, "utf-8", errors="ignore")
        _current_url = page.url
        _screenshot = await page.screenshot()
        _full_screenshot = await page.screenshot(full_page=True)

        result = ScraperOutput(
            request_url=url,
            url=_current_url,
            date=datetime.now(),
            body=_body,
            requests=_requests,
            screenshot=_screenshot,
            full_screenshot=_full_screenshot,
        )

        if self.clear_cookies:
            await self.context.clear_cookies()

        await page.close()

        return result

    async def close(self) -> None:
        if self.driver:
            await self.driver.close()
