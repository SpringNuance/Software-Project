from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
from typing import Tuple, List, Dict, Any, NamedTuple
from requests_html import HTML
from lxml import etree
from lxml.html.clean import Cleaner
from justext.core import ParagraphMaker
import trafilatura, orjson
import logging
import re

from ..utils.generic import Output

logging.getLogger("trafilatura").setLevel(logging.CRITICAL)

HTMLElementOutput = NamedTuple(
    "HTMLElementOutput", [("text", str), ("attrs", dict)]
)  # A `namedtuple` to store the text and attributes of an HTML element

HTMLFormOutput = NamedTuple(
    "HTMLFormOutput",
    [
        (
            "element",
            HTMLElementOutput,
        ),
        ("inputs", List[HTMLElementOutput]),
    ],
)  # A `namedtuple` to store the information about a form


@dataclass
class HTMLExtractorOutput(Output):
    """Dataclass for storing extracted information from HTML"""

    url: str = None
    date: datetime = None
    titles: List[str] = None
    meta: Dict[str, List[HTMLElementOutput]] = None
    urls: List[str] = None
    text: Dict[str, str] = None
    images: List[HTMLElementOutput] = None
    svgs: List[HTMLElementOutput] = None
    css: Dict[str, List[HTMLElementOutput]] = None
    js: Dict[str, List[HTMLElementOutput]] = None
    forms: List[HTMLFormOutput] = None
    iframes: List[HTMLElementOutput] = None
    stats: Dict[str, Any] = field(default_factory=dict)


class HTMLWrapper(HTML):
    """A wrapper around `requests_html`'s HTML to facilitate extracting information"""

    html_tag_re = re.compile(r"<([a-z]+)(?=[\s>])(?:[^>=]|='[^']*'|=\"[^\"]*\"|=[^'\"\s]*)*\s?\/?>", re.I | re.U)

    def get_urls(self, absolute: bool = True) -> List[str]:
        """Returns all links found in the page.

        :param absolute: Return URLs in absolute form, defaults to True.
        :type absolute: bool, optional
        :return: a list of URLs found in the page.
        :rtype: List[str]
        """
        return self.absolute_links if absolute else self.links

    def get_titles(self) -> List[str]:
        """Get all text inside <title>

        :return: A list of titles, in case multiple were present.
        :rtype: List[str]
        """
        return [_t.text for _t in self.find("title", clean=True)]

    def get_meta(self) -> Dict[str, List[HTMLElementOutput]]:
        """Get all meta data in the page. The meta data is grouped by `type`. When the type is not present, an empty string is used.

        :return: A dictionary containing all the meta information in the page.
        :rtype: Dict[str, List[HTMLElementOutput]]
        """
        meta = defaultdict(list)
        for _t in self.find("meta", clean=True):
            if "type" in _t.attrs:
                meta[_t.attrs["type"]].append(HTMLElementOutput(_t.text, _t.attrs))
            else:
                meta[""].append(HTMLElementOutput(_t.text, _t.attrs))
        return meta

    def get_js(self) -> Dict[str, List[HTMLElementOutput]]:
        """Returns all Javascript elements in the HTML.

        :return: A dictionary with `external` and `internal` keys representing whether the JS is embedded in the HTML or requested from an external source.
        :rtype: Dict[str, List[HTMLElementOutput]]
        """
        js = {"inline": [], "external": []}
        for _t in self.find("script"):
            if "src" in _t.attrs:
                js["external"].append(HTMLElementOutput(_t.text, _t.attrs))
            else:
                js["inline"].append(HTMLElementOutput(_t.text, _t.attrs))
        return js

    def get_css(self) -> Dict[str, List[HTMLElementOutput]]:
        """Returns all CSS elements in the HTML.

        :return: A dictionary with `external` and `internal` keys representing whether the CSS is embedded in the HTML or requested from an external source.
        :rtype: Dict[str, List[HTMLElementOutput]]
        """
        css = {"inline": [], "external": []}
        for _t in self.find("link[rel='stylesheet'], style"):
            if "href" in _t.attrs:
                css["external"].append(HTMLElementOutput(_t.text, _t.attrs))
            else:
                css["inline"].append(HTMLElementOutput(_t.text, _t.attrs))
        return css

    def get_images(self) -> List[HTMLElementOutput]:
        """Find all images in the HTML. Tags used to identify images are `img`, `amp-img`, `picture` and `source`

        :return: A list containing the image elements.
        :rtype: List[HTMLElementOutput]
        """
        return [HTMLElementOutput(_t.text, _t.attrs) for _t in self.find("img, amp-img, picture source")]

    def get_svgs(self) -> List[HTMLElementOutput]:
        """Find all SVG in the HTML.

        :return: A list containing the svg elements.
        :rtype: List[HTMLElementOutput]
        """
        return [HTMLElementOutput(_t.raw_html, _t.attrs) for _t in self.find("svg")]

    def get_forms(self) -> List[HTMLFormOutput]:
        """Finds all the `form`s in the HTML and returns them along with the input fields that are present in them.

        :return: A list of forms and their corresponding inputs.
        :rtype: List[HTMLFormOutput]
        """
        forms = []
        for form in self.find("form", clean=True):
            input_fields = form.find("input")

            forms.append(
                HTMLFormOutput(
                    HTMLElementOutput(form.full_text, form.attrs),
                    [HTMLElementOutput("", _f.attrs) for _f in input_fields],
                )
            )

        return forms

    def get_iframes(self) -> List[HTMLElementOutput]:
        """Finds all `iframe`s in the HTML and returns them.

        :return: A list of `HTMLElementOutput` containing the text and attributes of all `iframe` elements.
        :rtype: List[HTMLElementOutput]
        """
        return [HTMLElementOutput(_t.raw_html, _t.attrs) for _t in self.find("iframe")]

    def get_stats(self) -> Dict[str, Any]:
        """Calculate some statistics from the HTML.

        Current statistics:
        -) `total`: the total number of tags in the HTML
        -) `tags`: The count of each "interesting" tag.

        Can be included in the future:
        -) The depth of the HTML and certain important elements.


        :return: A dictionary containing the statistics
        :rtype: Dict[str, Any]
        """
        stats_summary = {}
        tags_counter = defaultdict(int)
        _tags_of_interest = (
            "div",
            "iframe",
            "script",
            "link",
            "style",
            "a",
            "p",
            "span",
            "svg",
            "table",
            "form",
            "input",
            "textarea",
            "video",
            "button",
            "code",
            "h1",
            "h2",
            "h3",
            "meta",
            "img",
            "li",
        )
        dom_str = etree.tostring(self.lxml).decode()

        matches = HTMLWrapper.html_tag_re.findall(dom_str)
        stats_summary["total"] = len(matches)
        for _tag in matches:
            if _tag in _tags_of_interest:
                tags_counter[_tag] += 1

        stats_summary["tags"] = tags_counter

        return tags_counter

    def get_text(self, dom=None) -> Dict[str, str]:
        """Extract the textual information from the page. There are two types of textual information being extracted at the moment:

        1) `full_text`: All the textual information that is in the page.
        2) `content`: Textual content without boilerplate data.

        :param dom: `lxml` element to extract the text from. When set to None, the `self` HTML is used instead, defaults to None
        :type dom: _type_, optional
        :return: A dictionary containing two keys (`full_text` and `content`).
        :rtype: Dict[str, str]
        """
        dom = dom if dom is not None else self.lxml
        paragraphs = ParagraphMaker.make_paragraphs(dom)

        dom_str = etree.tostring(dom)

        _extract = trafilatura.extract(
            dom_str,
            output_format="json",
            url=self.url,
            with_metadata=False,
            include_tables=True,
            include_images=False,
            include_comments=False,
            include_links=False,
            no_fallback=True,
        )

        return {
            "content": orjson.loads(_extract)["text"].split("\n") if _extract else "",
            "full_text": [_p.text for _p in paragraphs],
        }


class HTMLExtractor:
    """A class for extracting information from web pages (HTML)"""

    def __init__(self, *args, **kwargs):
        cleaner_options = {
            "processing_instructions": False,
            "remove_unknown_tags": False,
            "safe_attrs_only": False,
            "page_structure": False,
            "annoying_tags": False,
            "frames": False,
            "meta": False,
            "links": False,
            "javascript": False,
            "scripts": True,
            "comments": True,
            "style": True,
            "embedded": True,
            "forms": True,
            "kill_tags": ("head",),
        }
        self.cleaner = Cleaner(**cleaner_options)  # The cleaner for cleaning HTML to enhance extracting textual data

    def clean_html(self, dom):
        """Clean and return the `lxml` dom.

        :param dom: `lxml` dom.
        :type dom: _type_
        :return: The input `dom` after cleaning.
        :rtype: _type_
        """
        _clean = dom

        # ensure sanitization
        for _r in _clean.xpath(".//script | .//style"):
            _r.getparent().remove(_r)

        return self.cleaner.clean_html(_clean)

    def extract(self, html, url=None) -> HTMLExtractorOutput:
        r = HTMLWrapper(html=html, url=url)

        clean_body = r.find("body", first=True)

        clean_lxml = self.clean_html(clean_body.lxml) if clean_body else None

        result = HTMLExtractorOutput(
            url=url,
            date=datetime.now(),
            titles=r.get_titles(),
            meta=r.get_meta(),
            urls=r.get_urls(),
            text=r.get_text(clean_lxml),
            images=r.get_images(),
            svgs=r.get_svgs(),
            css=r.get_css(),
            js=r.get_js(),
            forms=r.get_forms(),
            iframes=r.get_iframes(),
            stats=r.get_stats(),
        )

        return result

    def process_css(self, css):
        raise NotImplementedError("`process_css` not implemented, consider implementing it.")

    def process_js(self, js):
        raise NotImplementedError("`process_css` not implemented, consider implementing it.")
