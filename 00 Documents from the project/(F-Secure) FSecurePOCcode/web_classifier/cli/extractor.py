from argparse import ArgumentParser
from multiprocessing import cpu_count
import tqdm
from tqdm.contrib.concurrent import process_map
import logging
import io
import os
import orjson

from web_classifier.utils.generic import chunks
from web_classifier.utils.files import get_num_lines
from web_classifier.extractors.html_extractor import HTMLExtractor, HTMLExtractorOutput

logger = logging.getLogger(__name__)

e = HTMLExtractor()


def extraction_task(row) -> HTMLExtractorOutput:
    row = orjson.loads(row)
    if not row["body"] or not row["body"][-7:].strip().endswith("</html>"):
        return None
    try:
        processed_row = e.extract(html=row["body"], url=row["url"])
        return processed_row.to_json()
    except:
        return None


def parse_cli_arguments():
    argument_parser = ArgumentParser(description="")

    argument_parser.add_argument("-i", "--input", dest="input", required=True, help="File containing the URLs.")

    argument_parser.add_argument("-o", "--output", dest="output", required=True, help="Output file.")

    argument_parser.add_argument(
        "--num_workers", default=cpu_count(), type=int, help="Number of workers to process dataset."
    )

    argument_parser.add_argument("--batch_size", default=100, type=int, help="The batch/chunk size.")

    return argument_parser.parse_args()


def main():
    args = parse_cli_arguments()

    data_size = get_num_lines(args.input)
    chunk_size = args.num_workers * args.batch_size

    pbar = tqdm.tqdm(total=data_size)

    with io.open(args.input, "r", encoding="utf-8") as input_fp, io.open(args.output, "wb") as output_fp:
        for batch in chunks(input_fp, chunk_size):
            data = process_map(
                extraction_task, batch, max_workers=args.num_workers, chunksize=args.batch_size, disable=True
            )
            for item in data:
                if not item:
                    continue

                output_fp.write(item)
                output_fp.write(bytes(os.linesep, encoding="utf-8"))

            pbar.update(chunk_size)

        output_fp.truncate(output_fp.tell() - len(os.linesep))

    pbar.close()


if __name__ == "__main__":
    main()
