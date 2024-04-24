import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from datetime import datetime
from argparse import ArgumentParser, BooleanOptionalAction

from ..service import ServiceInterface
from ..utils.generic import Output


@dataclass
class ResponseOutput(Output):
    """A dataclass to store the output of a response"""

    body: bytes = None  # Response body
    date: datetime = None  # When the response was received
    headers: Dict[str, str] = None  # Headers
    status_code: str = None  # Status code
    reason: str = None  # Status reason


@dataclass
class RequestOutput(Output):
    """A dataclass to store the details of a request"""

    url: str = None  # Requested URL
    body: bytes = None  # Request body
    cert: Dict[str, str] = None  # Certificate information
    date: datetime = None  # When the request was sent
    headers: Dict[str, str] = None  # Request headers
    host: str = None  # Requested host
    method: str = None  # Method type
    params: str = None  # Parameters
    path: str = None  # Path of URL
    resource_type: str = None  # The type of the resource requested
    response: ResponseOutput = None  # Returned response


@dataclass
class ScraperOutput(Output):
    request_url: str = None  # Requested URL
    url: str = None  # URL after redirects
    date: datetime = None  # The date of the scrape
    body: bytes = None  # The final content of page
    requests: Optional[Tuple[RequestOutput]] = None  # All requests sent by requesting the URL
    screenshot: Optional[bytes] = None  # Screenshot of the visible area of the rendered page
    full_screenshot: Optional[bytes] = None  # Screenshot of the full page


class Scraper(ServiceInterface):
    """The base class for different scrappers"""

    def __init__(self, *, timeout=3000, headers: Tuple[str] = None, user_agent=None, proxy: str = None, **kwargs):
        """Initialize the base scraper

        :param timeout: Maximum time to wait, defaults to 3000
        :type timeout: int, optional
        :param headers: Custom headers to set when sending the request, defaults to None
        :type headers: Tuple[str], optional
        :param user_agent: User agent, defaults to None
        :type user_agent: _type_, optional
        :param proxy: Proxy to use, defaults to None
        :type proxy: str, optional
        """
        self.timeout = timeout
        self.headers = headers
        self.user_agent = user_agent
        self.proxy = proxy

    @staticmethod
    def add_args(argument_parser: ArgumentParser):
        argument_parser.add_argument("--timeout", dest="timeout", type=int, required=False, default=3000, help="")

        argument_parser.add_argument("--headers", dest="headers", type=str, required=False, action="append", help="")

        argument_parser.add_argument("--user_agent", dest="user_agent", type=str, default=None)

        argument_parser.add_argument(
            "--proxy",
            dest="proxy",
            default=None,
            type=str,
            help="Proxy (e.g., http://localhost:port)",
        )

    def setup(self) -> None:
        """Setup the scraper"""
        raise NotImplementedError(f"Function `setup` not implemented in {self.__class__.__name__}.")

    def scrape(self, url: str) -> ScraperOutput:
        """Scrape a single URL"""
        raise NotImplementedError(f"Function `scrape` not implemented in {self.__class__.__name__}.")

    def close(self) -> None:
        """Close and clean the resources used by the scraper"""
        raise NotImplementedError(f"Function `close` not implemented in {self.__class__.__name__}.")


class BrowserScraper(Scraper):
    """Base class for browser-based scrapers"""

    def __init__(
        self,
        *,
        headless=True,
        use_gpu=False,
        implicit_wait: int = 0,
        browser="chrome",
        mobile: str = None,
        block_exts: Tuple[str] = (),
        allow_exts: Tuple[str] = (),
        clear_cookies: bool = True,
        with_requests: bool = True,
        with_extensions: str = None,
        **kwargs,
    ):
        """
        Initialize the scraper.

        :param headless: Whether to run the browser in headed or headless mode, defaults to True
        :type headless: bool, optional
        :param use_gpu: Should the rendering be accelerated by the GPU, defaults to False
        :type use_gpu: bool, optional
        :param implicit_wait: Time to implicitly wait for when rendering a page, defaults to 0
        :type implicit_wait: int, optional
        :param browser: The browser to use, defaults to "chrome"
        :type browser: str, optional
        :param mobile: The name of the mobile device to emulate, defaults to None
        :type mobile: str, optional
        :param block_exts: Extensions to block when sending requests during rendering.
            Blocking certain extensions speed up the rendering time but would affect the final result, defaults to ()
        :type block_exts: Tuple[str], optional
        :param allow_exts: Extensions to allow when sending requests during rendering.
            Allowing certain extensions only speed up the rendering time but would affect the final result, defaults to (), defaults to ()
        :type allow_exts: Tuple[str], optional
        :param clear_cookies: Whether to clear the cookies after rendering each page, defaults to True
        :type clear_cookies: bool, optional
        :param with_requests: Whether to process the requests and return them, defaults to True
        :type with_requests: bool, optional
        :param with_extensions: Path to the extensions to be loaded by the browser (comma separated).
        :type with_extensions: str, optional
        """
        self.headless = headless
        self.use_gpu = use_gpu
        self.implicit_wait = implicit_wait
        self.browser = browser
        self.mobile = mobile
        self.allow_exts = allow_exts
        self.block_exts = block_exts
        self.clear_cookies = clear_cookies
        self.with_requests = with_requests
        self.with_extensions = with_extensions

        self.driver = None
        self.context = None

        super(BrowserScraper, self).__init__(**kwargs)

    @staticmethod
    def add_args(argument_parser: ArgumentParser):
        super(BrowserScraper, BrowserScraper).add_args(argument_parser=argument_parser)
        argument_parser.add_argument(
            "--headless",
            dest="headless",
            default=True,
            type=bool,
            action=BooleanOptionalAction,
            required=False,
            help="The driver to use for rendering.",
        )

        argument_parser.add_argument(
            "--use-gpu",
            dest="use_gpu",
            default=False,
            type=bool,
            action=BooleanOptionalAction,
            required=False,
            help="Whether to use the GPU for rendering.",
        )

        argument_parser.add_argument(
            "--browser",
            dest="browser",
            default="chrome",
            choices=[
                "chrome",
            ],
            help="What browser to use.",
        )

        argument_parser.add_argument(
            "--mobile",
            dest="mobile",
            default=False,
            type=bool,
            action=BooleanOptionalAction,
            required=False,
            help="Whether to render the mobile.",
        )

        argument_parser.add_argument(
            "--allow_exts",
            dest="allow_exts",
            nargs="?",
            default=(),
            required=False,
            help="File extensions to allow.",
        )

        argument_parser.add_argument(
            "--block_exts",
            dest="block_exts",
            nargs="?",
            default=(),
            required=False,
            help="File extensions to block.",
        )

        argument_parser.add_argument(
            "--implicit_wait",
            dest="implicit_wait",
            required=False,
            type=int,
            default=0,
            help="Time to wait (in ms) for the rendering to complete.",
        )
