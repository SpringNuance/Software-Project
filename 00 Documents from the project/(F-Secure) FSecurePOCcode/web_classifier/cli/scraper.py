from argparse import ArgumentParser
import asyncio
import aiofiles
import logging
import io
import os
from datetime import datetime
from typing import List
from tqdm import tqdm
import pycurl
from playwright.async_api import async_playwright

from web_classifier.scrapers import CurlScraper, CurlWrapper, PlaywrightScraper
from web_classifier.utils.generic import get_urls


logger = logging.getLogger(__name__)


def strip_data(data, to_strip=(), keep_request_type=()):
    """Clean the result to reduce space when saving."""
    for _var in to_strip:
        if _var == "requests" and keep_request_type:
            data[_var] = [_r for _r in data[_var] if _r.resource_type in keep_request_type]
        elif _var in data:
            if isinstance(data[_var], (list, tuple)):
                data[_var] = []
            elif isinstance(data[_var], dict):
                data[_var] = {}
            else:
                data[_var] = None
    return data


def convert_data(data):
    """Convert the data into json"""
    return data.to_json()


def _curl_main(*args, **kwargs):
    """The main function for scraping URLs using cURL.
    Based on: https://github.com/pycurl/pycurl/blob/master/examples/retriever-multi.py
    """

    scrapper = CurlScraper(**kwargs)

    num_conn = kwargs.get("num_conn")

    assert 1 <= num_conn <= 10000, "invalid number of concurrent connections"

    urls = get_urls(kwargs.get("input"))
    to_strip = kwargs.get("strip_data").split()
    content_to_keep = kwargs.get("keep_content").split()

    output_file = kwargs.get("output")
    output_fp = io.open(output_file, "wb")

    queue = urls

    # Check args
    num_urls = len(queue)
    num_conn = min(num_conn, num_urls)

    pbar = tqdm(total=num_urls)
    start_time = datetime.now()

    # Pre-allocate a list of curl objects
    m = pycurl.CurlMulti()
    m.handles = []
    for _ in range(num_conn):
        c = scrapper._curl_instance()
        m.handles.append(c)

    # Main loop
    freelist = m.handles[:]
    num_processed = 0
    while num_processed < num_urls:
        # If there is an url to process and a free curl object, add to multi stack
        while queue and freelist:
            url = queue.pop(0)

            c = freelist.pop()

            cw = CurlWrapper(c)

            cw.assign(url)

            c.cw = cw

            m.add_handle(c)

        # Run the internal curl state machine for the multi stack
        while 1:
            ret, num_handles = m.perform()
            if ret != pycurl.E_CALL_MULTI_PERFORM:
                break

        # Check for curl objects which have terminated, and add them to the freelist
        while 1:
            num_q, ok_list, err_list = m.info_read()

            for c in ok_list:
                data = c.cw.get_result()

                m.remove_handle(c)

                data = strip_data(data, to_strip, content_to_keep)

                data = convert_data(data)

                output_fp.write(data)

                output_fp.write(bytes(os.linesep, encoding="utf-8"))

                freelist.append(c)

                pbar.update(1)  # update progress bar

            for c, errno, errmsg in err_list:
                m.remove_handle(c)

                freelist.append(c)

                pbar.update(1)  # update progress bar

            num_processed = num_processed + len(ok_list) + len(err_list)
            if num_q == 0:
                break
        # Currently no more I/O is pending, could do something in the meantime
        # (display a progress bar, etc.).
        # We just call select() to sleep until some more data is available.
        m.select(1.0)

    # Cleanup
    for c in m.handles:
        c.close()

    m.close()

    pbar.close()

    output_fp.truncate(output_fp.tell() - len(os.linesep))
    output_fp.close()

    end_time = datetime.now()

    diff = end_time - start_time

    logger.info(f"Process finished in {diff.total_seconds()} seconds")


async def _playwright_scrape_task(scraper: PlaywrightScraper, url, to_strip=(), to_keep=()):
    """Task for scraping a single page"""

    data = await scraper.scrape(url)

    data = strip_data(data, to_strip, to_keep)

    data = convert_data(data)

    return data


async def _playwright_worker(queue, scraper, to_strip, content_to_keep, fp, pbar):
    """A worker in charge of managing a single page in the browser instance"""
    while True:
        url = await queue.get()

        if url is None:  # no more urls
            return

        try:
            data = await _playwright_scrape_task(scraper, url, to_strip, content_to_keep)

            await fp.write(data)
            await fp.write(bytes(os.linesep, encoding="utf-8"))

        except Exception as e:
            pass  # ignore any errors
        finally:
            pbar.update(1)  # update progress bar
            queue.task_done()  # indicate that the task is done


async def _playwright_main(*args, **kwargs):
    """Main for scraping URLs using playwright asynchronously."""

    urls = get_urls(kwargs.get("input"))
    output_file = kwargs.get("output")

    to_strip = kwargs.get("strip_data").split()
    content_to_keep = kwargs.get("keep_content").split()
    num_pages = kwargs.get("num_pages")

    start_time = datetime.now()

    s = PlaywrightScraper(**kwargs)

    async with async_playwright() as playwright:
        await s.setup(playwright)

        job_queue = asyncio.Queue()

        pbar = tqdm(total=len(urls))

        worker_tasks = []

        try:
            async with aiofiles.open(output_file, "wb") as output_fp:
                async with asyncio.TaskGroup() as tg:
                    for _ in range(num_pages):
                        wt = tg.create_task(
                            _playwright_worker(job_queue, s, to_strip, content_to_keep, output_fp, pbar)
                        )
                        worker_tasks.append(wt)

                    for url in urls:
                        await job_queue.put(url)

                    for _ in range(num_pages):
                        await job_queue.put(None)

                    await job_queue.join()

                _tell = await output_fp.tell()
                await output_fp.truncate(_tell - len(os.linesep))

        except* Exception as e:
            pass

        finally:
            pass

        pbar.close()

        await s.close()

    end_time = datetime.now()

    diff = end_time - start_time

    logger.info(f"Process finished in {diff.total_seconds()} seconds")


def parse_cli_arguments():
    argument_parser = ArgumentParser(description="")

    argument_parser.add_argument("-i", "--input", dest="input", required=True, help="File containing the URLs.")

    argument_parser.add_argument("-o", "--output", dest="output", required=True, help="Output file.")

    argument_parser.add_argument(
        "--strip-data",
        dest="strip_data",
        type=str,
        default="",
        nargs="?",
        required=False,
        help="What parts of the data to omit.",
    )

    argument_parser.add_argument(
        "--keep-content",
        dest="keep_content",
        type=str,
        default="",
        nargs="?",
        choices=(
            "document",
            "stylesheet",
            "image",
            "media",
            "font",
            "script",
            "texttrack",
            "xhr",
            "fetch",
            "eventsource",
            "websocket",
            "manifest",
            "other",
        ),
        required=False,
        help="Which content types to keep.",
    )

    argument_parser.add_argument(
        "-s",
        "--scraper",
        dest="scraper",
        type=str,
        default="curl",
        required=False,
        choices=["curl", "playwright"],
        help="The scraper to use.",
    )

    main_args, _ = argument_parser.parse_known_args()

    if main_args.scraper == "curl":
        argument_parser.add_argument(
            "--num_conn", dest="num_conn", type=int, default=10, help="Number of concurrent connections to use."
        )

        CurlScraper.add_args(argument_parser)
    elif main_args.scraper == "playwright":
        argument_parser.add_argument(
            "--num_pages",
            dest="num_pages",
            type=int,
            default=10,
            help="Number of pages to open concurrently per browser.",
        )

        PlaywrightScraper.add_args(argument_parser)

    return argument_parser.parse_args()


def main():
    args = parse_cli_arguments()

    if args.scraper == "curl":
        _curl_main(**args.__dict__)
    elif args.scraper == "playwright":
        asyncio.run(_playwright_main(**args.__dict__))


if __name__ == "__main__":
    main()
