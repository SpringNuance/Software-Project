import io
from pathlib import Path
from typing import Union, List
import subprocess
import hashlib


def get_lines(filepath: Union[Path, str]) -> List[str]:
    """A function that reads a file and returns its lines.

    :param filepath: File path.
    :type filepath: Union[Path, str]
    :return: Lines in the file.
    :rtype: List[str]
    """
    with io.open(filepath, "r", encoding="utf-8") as input_file:
        return input_file.readlines()


def get_num_lines(filepath: Union[Path, str]) -> int:
    """A function that counts the number of lines in a big file.

    Based on: https://stackoverflow.com/questions/9629179/python-counting-lines-in-a-huge-10gb-file-as-fast-as-possible

    :param filepath: File path.
    :type filepath: Union[Path, str]
    :return: Number of lines.
    :rtype: int
    """
    try:
        wc_output = subprocess.check_output(
            ["/usr/bin/wc", "-l", str(filepath)],
            text=True,
        )
        _size = int(wc_output.split()[0])
    except Exception as e:
        fp = open(filepath, "rb")
        _size = sum(1 for _ in fp)
        fp.close()
    return _size


def sha1sum(content: str):
    sha1 = hashlib.sha1(content)
    return sha1.hexdigest()
