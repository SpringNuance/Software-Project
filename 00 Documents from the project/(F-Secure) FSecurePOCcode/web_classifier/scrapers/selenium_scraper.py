from selenium.webdriver.common.by import By
from seleniumwire import webdriver

from ..scrapers.base import *


class SeleniumScraper(BrowserScraper):
    """Scrape web pages using selenium"""

    def setup(self) -> None:
        self.driver_options = webdriver.ChromeOptions()
        if self.headless:
            self.driver_options.add_argument("--headless")

        if not self.browser or self.browser == "chrome":
            self.driver_type = webdriver.Chrome
        else:
            raise Exception("Browser not known/supported.")

        if self.mobile:
            # for mobile options: https://sites.google.com/a/chromium.org/chromedriver/mobile-emulation
            # alternatively, "deviceMetrics": { "width": 360, "height": 640, "pixelRatio": 3.0 },
            self.driver_options.add_experimental_option("mobileEmulation", {"deviceName": self.mobile})

        self.driver = self.driver_type(chrome_options=self.driver_options)

        def interceptor(request):
            if not request.path.endswith(self.allow_exts) and request.path.endswith(self.block_exts):
                request.abort()

        if self.block_exts:
            self.driver.request_interceptor = interceptor

        if self.implicit_wait:
            self.driver.implicitly_wait(self.implicit_wait)

        self.driver.maximize_window()

    def scrape(self, url: str) -> ScraperOutput:
        self.driver.get(url)

        _body = self.driver.page_source  # `page_source` only works if the page completely loads
        if not _body:
            _body = self.driver.execute_script("return document.documentElement.innerHTML;")

        _body = bytes(_body, "utf-8", errors="ignore")  # make body type consistent

        _current_url = self.driver.current_url

        _requests = []
        for _r in self.driver.requests:
            if _r.response:
                _response = ResponseOutput(
                    body=_r.response.body,
                    date=_r.response.date,
                    headers=_r.response.headers,
                    status_code=_r.response.status_code,
                    reason=_r.response.reason,
                )
            else:
                _response = None

            _request = RequestOutput(
                url=_r.url,
                body=_r.body,
                cert=_r.cert,
                date=_r.date,
                headers=_r.headers,
                host=_r.host,
                method=_r.method,
                params=_r.params,
                path=_r.path,
                response=_response,
            )

            _requests.append(_request)

        _screenshot = self.driver.get_screenshot_as_png()
        _full_screenshot = self.driver.find_element(By.TAG_NAME, value="body").screenshot_as_png

        if self.clear_cookies:
            # to clear cache: https://stackoverflow.com/a/72922584
            self.driver.delete_all_cookies()

        result = ScraperOutput(
            request_url=url,
            url=_current_url,
            date=datetime.now(),
            body=_body,
            requests=_requests,
            screenshot=_screenshot,
            full_screenshot=_full_screenshot,
        )

        return result

    def close(self) -> None:
        self.driver.quit()
