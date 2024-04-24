from collections import OrderedDict
from typing import Any, List, Tuple, Union
import dataclasses
import orjson
import datetime
from base64 import b64encode
from pathlib import Path
from itertools import chain, islice

from .urls import is_url_valid
from ..utils.files import get_lines


def get_urls(filepath: List[Union[Path, str]]) -> List[str]:
    """Get valid urls from a file

    :param filepath: File path containing a URL per line.
    :type filepath: str
    :return: Valid URLs in the file.
    :rtype: List[str]
    """
    return [_url.strip() for _url in get_lines(filepath) if _url and _url[0] != "#" and is_url_valid(_url)]


def chunks(iterable, size=10):
    iterator = iter(iterable)
    for first in iterator:
        yield chain([first], islice(iterator, size - 1))


def default_json_encoder(obj: Any) -> Any:
    """Encodes an object to be compatible with JSON.

    :param obj: Object to encode
    :type obj: Any
    :raises TypeError: When the type is not encodable
    :return: The `obj` in a compatible format (e.g., string).
    :rtype: Any
    """
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, tuple) and hasattr(obj, "_asdict"):
        return obj._asdict()
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except:
            return b64encode(obj).decode()
    raise TypeError


def json_dumps(obj: Any, **kwargs) -> str:
    """Encode the object into a json string

    :param obj: The object to be encoded.
    :type obj: Any
    :return: The encoded object.
    :rtype: str
    """
    return orjson.dumps(obj, default=default_json_encoder, option=orjson.OPT_SERIALIZE_NUMPY, **kwargs)


class Output(OrderedDict):
    """A class that is used to represent outputs by different tools.
    Outputs can be accessed as dictionary and object variables. It also
    allows converting the data into JSON easily.
    """

    def __post_init__(self):
        """Initialize the data of the object"""

        class_fields = dataclasses.fields(self)
        field_names = {field.name for field in class_fields}
        first_field = getattr(self, class_fields[0].name)
        other_fields_are_none = all(getattr(self, field.name) is None for field in class_fields[1:])

        if isinstance(first_field, dict):
            iterator = first_field.items()
            first_field_iterator = True
        else:
            try:
                iterator = iter(first_field)
                first_field_iterator = True
            except TypeError:
                first_field_iterator = False

        if first_field_iterator and other_fields_are_none:
            # if the first input is an iterator and the rest aren't set
            # -> check if the iterator corresponds to the variables of the object and set them

            _copy = OrderedDict(iterator)
            self.clear()

            has_unknown_keys = len(set(_copy.keys()) - field_names) > 0

            for field in dataclasses.fields(self):
                v = getattr(self, field.name)
                if not has_unknown_keys and field.name in _copy:
                    self[field.name] = _copy[field.name]
                elif v:
                    self[field.name] = v
                else:
                    self[field.name] = field.default

        else:
            for field in class_fields:
                self[field.name] = getattr(self, field.name)

    def __delitem__(self, *args, **kwargs):
        raise Exception(f"Cannot use ``__delitem__`` on a {self.__class__.__name__} instance.")

    def setdefault(self, *args, **kwargs):
        raise Exception(f"Cannot use ``setdefault`` on a {self.__class__.__name__} instance.")

    def pop(self, *args, **kwargs):
        raise Exception(f"Cannot use ``pop`` on a {self.__class__.__name__} instance.")

    def update(self, *args, **kwargs):
        raise Exception(f"Cannot use ``update`` on a {self.__class__.__name__} instance.")

    def __getitem__(self, k):
        if isinstance(k, str):
            inner_dict = {k: v for (k, v) in self.items()}
            return inner_dict[k]
        else:
            return self.to_tuple()[k]

    def __setattr__(self, name, value):
        if name in self.keys() and value is not None:
            super().__setitem__(name, value)
        super().__setattr__(name, value)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        super().__setattr__(key, value)

    def to_tuple(self) -> Tuple[Any]:
        return tuple(self[k] for k in self.keys())

    def to_json(self, **kwargs) -> str:
        """Convert the object into JSON.

        :return: A valid JSON representation of the object.
        :rtype: str
        """
        return json_dumps(self, **kwargs)
