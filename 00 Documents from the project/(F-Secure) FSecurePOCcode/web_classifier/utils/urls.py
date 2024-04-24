import re
from urllib.parse import urlparse, urlsplit
import tldextract

_url_valid_regex = re.compile(
    r"^(?:http|ftp)s?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)

_url_img_regex = re.compile(r"(.*)\.(jpe?g|png|bmp)$", re.I | re.U)


def is_url_valid(url: str) -> bool:
    """Check whether a URL is a valid one.
    Based on: https://github.com/django/django/blob/stable/1.3.x/django/core/validators.py#L45

    :param url: URL to validate.
    :type url: str
    :return: Whether the URL is valid or not.
    :rtype: bool
    """
    return _url_valid_regex.match(url) is not None


def is_url_image(url: str) -> bool:
    """Checks whether the URL is an image or not.

    :param url: URL to check.
    :type url: str
    :return: An image or not
    :rtype: bool
    """
    parsed_url = urlparse(url)
    return _url_img_regex.match(parsed_url.path) is not None


def get_domain(url: str) -> str:
    """Returns the second-level domain (SLD) with the top-level domain (TLD)

    :param url: url to get the main domain from.
    :type url: str
    :return: sld.tld
    :rtype: str
    """
    netloc = urlsplit(url)[1]
    domain = ".".join(part for part in tldextract.extract(netloc)[-2:] if part)
    return domain
