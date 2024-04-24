import pycurl
from urllib.parse import urlparse
import certifi
from io import BytesIO

from ..scrapers.base import *


class CurlWrapper:
    """A wrapper around a cURL object."""

    def __init__(self, curl: pycurl.Curl) -> None:
        self.curl = curl
        self.bytes = BytesIO()
        self.headers = {}
        self.url = None

    def header_function(self, header_line):
        """A function to convert the headers into a dictionary."""

        header_line = header_line.decode("iso-8859-1")
        if ":" not in header_line:
            return
        name, value = header_line.split(":", 1)
        name = name.strip()
        value = value.strip()
        name = name.lower()
        self.headers[name] = value

    def assign(self, url):
        """Assign a URL to the cURL object"""
        self.url = url

        self.curl.setopt(pycurl.URL, self.url)

        self.curl.setopt(pycurl.WRITEDATA, self.bytes)

        self.curl.setopt(pycurl.HEADERFUNCTION, self.header_function)

    def get_result(self) -> ScraperOutput:
        """Get the information and result of the performed cURL request

        :return: Scraping result
        :rtype: ScraperOutput
        """
        _current_url = self.curl.getinfo(pycurl.EFFECTIVE_URL)

        certinfo = self.curl.getinfo(pycurl.INFO_CERTINFO)
        certinfo_dict = {}
        for entry in certinfo:
            certinfo_dict[entry[0]] = entry[1]

        _body = self.bytes.getvalue()

        _request = RequestOutput(
            url=_current_url,
            date=datetime.now(),
            cert=certinfo_dict,
            response=ResponseOutput(
                body=_body,
                date=datetime.now(),
                headers=self.headers,
                status_code=self.curl.getinfo(pycurl.HTTP_CODE),
            ),
        )

        result = ScraperOutput(
            request_url=self.url,
            url=_current_url,
            date=datetime.now(),
            requests=(_request,),
            body=_body,
        )

        return result


class CurlScraper(Scraper):
    """Scraper that uses cURL."""

    def __init__(
        self,
        *,
        cookie_file="",
        allow_redirects=True,
        max_redirects=3,
        no_ssl: bool = False,
        **kwargs,
    ):
        """Initialize the cURL scraper.

        :param cookie_file: The file to use for storing cookies, defaults to ""
        :type cookie_file: str, optional
        :param allow_redirects: Whether redirects should be followed, defaults to True
        :type allow_redirects: bool, optional
        :param max_redirects: Maximum number of redirects, defaults to 3
        :type max_redirects: int, optional
        :param no_ssl: Do not validate SSL requests, defaults to False
        :type no_ssl: bool, optional
        """
        self.cookie_file = cookie_file
        self.allow_redirects = allow_redirects
        self.max_redirects = max_redirects
        self.no_ssl = no_ssl

        self.curl_options = []
        super(CurlScraper, self).__init__(**kwargs)

    @staticmethod
    def add_args(argument_parser: ArgumentParser):
        super(CurlScraper, CurlScraper).add_args(argument_parser=argument_parser)

        argument_parser.add_argument("--cookie_file", dest="cookie_file", type=str, default="")
        argument_parser.add_argument(
            "--allow_redirects", dest="allow_redirects", type=bool, action=BooleanOptionalAction, default=True
        )
        argument_parser.add_argument("--max_redirects", dest="max_redirects", type=int, default=3)
        argument_parser.add_argument("--no_ssl", dest="no_ssl", type=bool, action=BooleanOptionalAction, default=False)

    def _add_curl_option(self, name, value):
        self.curl_options.append((name, value))

    def setup(self):
        self.curl_share = pycurl.CurlShare()  # object to share information among different cURL objects
        self.curl_share.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_DNS)  # DNS cache
        self.curl_share.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_SSL_SESSION)  # SSL session ID cache
        # self.curl_share.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_CONNECT) # shared connection cache, not thread-safe
        self._add_curl_option(pycurl.SHARE, self.curl_share)  # let handles share the DNS cache & SSL sessions

        if self.proxy:  # set up the proxy if defined
            parsed_proxy = urlparse(self.proxy)

            self._add_curl_option(pycurl.PROXY, f"{parsed_proxy.scheme}://{parsed_proxy.hostname}")
            self._add_curl_option(pycurl.PROXYPORT, parsed_proxy.port)

            PROXIES_TYPES_MAP = {
                "socks5": pycurl.PROXYTYPE_SOCKS5,
                "socks4": pycurl.PROXYTYPE_SOCKS4,
                "http": pycurl.PROXYTYPE_HTTP,
                "https": pycurl.PROXYTYPE_HTTP,
            }

            self._add_curl_option.setopt(pycurl.PROXYTYPE, PROXIES_TYPES_MAP[parsed_proxy.scheme])

            if parsed_proxy.scheme == "http":
                self._add_curl_option.setopt(pycurl.PROXY_SSL_VERIFYHOST, 0)
                self._add_curl_option.setopt(pycurl.PROXY_SSL_VERIFYPEER, 0)

        if self.headers:
            self._add_curl_option(pycurl.HTTPHEADER, self.headers)

        if self.cookie_file is not None:
            self._add_curl_option(pycurl.COOKIEFILE, self.cookie_file)

        if self.user_agent:
            self._add_curl_option(pycurl.USERAGENT, self.user_agent)

        if self.no_ssl:
            self._add_curl_option(pycurl.SSL_VERIFYPEER, 0)
            self._add_curl_option(pycurl.SSL_VERIFYHOST, 0)
        else:
            self._add_curl_option(pycurl.SSL_VERIFYPEER, 1)
            self._add_curl_option(pycurl.SSL_VERIFYHOST, 2)
            self._add_curl_option(pycurl.CAINFO, certifi.where())

        if self.allow_redirects:
            self._add_curl_option(pycurl.FOLLOWLOCATION, self.allow_redirects)
            self._add_curl_option(pycurl.MAXREDIRS, self.max_redirects)

        self._add_curl_option(pycurl.CONNECTTIMEOUT, 30)
        self._add_curl_option(pycurl.NOSIGNAL, 1)

        if self.timeout is not None:
            self._add_curl_option(pycurl.TIMEOUT, self.timeout)

    def _curl_instance(self) -> pycurl.Curl:
        c = pycurl.Curl()

        for opt in self.curl_options:  # set all options
            c.setopt(*opt)

        return c

    def scrape(self, url: str):
        c = self._curl_instance()

        cw = CurlWrapper(c)

        cw.assign(url=url)

        c.perform()

        result = cw.get_result()

        c.close()

        return result

    def close(self) -> None:
        pass  # nothing to close
