import datetime
import json
import logging
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from opentelemetry_wrapper.utils.json_encoder import jsonable_encoder


class JsonFormatter(logging.Formatter):
    """
    converts a LogRecord to a JSON string
    """

    def __init__(self,
                 keys: Optional[Union[Tuple[str, ...], List[str], Dict[str, str]]] = None,
                 *,
                 datefmt: Optional[str] = None,
                 ensure_ascii: bool = False,
                 allow_nan: bool = True,
                 indent: Optional[int] = None,
                 separators: Optional[Tuple[str, str]] = None,
                 sort_keys: bool = False,
                 max_string_length: int = 10000,
                 ) -> None:
        """
        see https://docs.python.org/3/library/logging.html#logrecord-attributes for record keys
        (opentelemetry also adds `otelSpanID`, `otelTraceID`, and `otelServiceName`)

        :param keys: list of LogRecord attributes, or mapper from LogRecord attribute name -> output json key name
        :param datefmt: date format string; if not set, defaults to ISO8601
        :param ensure_ascii: see `json.dumps` docs
        :param allow_nan: see `json.dumps` docs
        :param indent: see `json.dumps` docs
        :param separators: see `json.dumps` docs
        :param sort_keys: see `json.dumps` docs
        :param max_string_length: truncate string values (not keys) longer than this
        """

        super().__init__(datefmt)

        self._keys: Optional[Dict[str, str]]
        if isinstance(keys, dict):
            self._keys = dict()
            self._keys.update(keys)
        elif not isinstance(keys, str) and isinstance(keys, Iterable):
            self._keys = dict()
            for key in keys:
                assert isinstance(key, str), key
                self._keys[key] = key
        elif keys is None:
            self._keys = None
        else:
            raise TypeError(keys)

        self.ensure_ascii = ensure_ascii
        self.allow_nan = allow_nan
        self.indent = indent
        self.separators = separators
        self.sort_keys = sort_keys

        # noinspection PyTypeChecker
        self.tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

        self.max_string_length = max_string_length

    def usesTime(self):
        return self._keys is None or 'asctime' in self._keys

    def formatMessage(self, record: logging.LogRecord):
        raise DeprecationWarning

    # flake8: noqa: C901
    def format(self, record):
        """
        Format the specified record as text.

        The record's attribute dictionary is used as the operand to a
        string formatting operation which yields the returned string.
        Before formatting the dictionary, a couple of preparatory steps
        are carried out. The message attribute of the record is computed
        using LogRecord.getMessage(). If the formatting string uses the
        time (as determined by a call to usesTime(), formatTime() is
        called to format the event time. If there is exception information,
        it is formatted using formatException() and appended to the message.
        """
        # add `message` but catch errors
        try:
            record.message = record.getMessage()
        except TypeError:
            record.message = f'MSG={repr(record.msg)} ARGS={repr(record.args)}'

        # add `asctime`, `tz_name`, and `tz_utc_offset_seconds`
        if self.usesTime():
            record.tz_name = self.tz.tzname(None)
            record.tz_utc_offset_seconds = self.tz.utcoffset(None).seconds
            if self.datefmt:
                record.asctime = self.formatTime(record, self.datefmt)
            else:
                record.asctime = datetime.datetime.fromtimestamp(record.created, tz=self.tz).isoformat()

        # add `exc_text`
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)

        if self._keys is not None:
            log_data = {k: getattr(record, v, None) for k, v in self._keys.items()}
        else:
            log_data = record.__dict__

        # noinspection PyBroadException
        try:
            safe_log_data = jsonable_encoder(log_data)

        # failsafe: stringify everything using `repr()`
        except Exception:
            safe_log_data = dict()
            for k, v in log_data.items():

                # stringify key
                if not isinstance(k, str):
                    # noinspection PyBroadException
                    try:
                        k = repr(k)
                    except Exception:
                        continue  # failed, skip key

                # encode value
                if isinstance(v, (int, float, bool, str, type(None))):
                    safe_log_data[k] = v
                else:
                    # noinspection PyBroadException
                    try:
                        safe_log_data[k] = repr(v)
                    except Exception:
                        continue  # failed, skip key

        # truncate extremely long strings (values nested in dicts and lists, but not dict keys)
        stack = [safe_log_data]
        while stack:
            elem = stack.pop()
            if isinstance(elem, dict):
                for k, v in elem.items():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
                    if isinstance(v, str) and len(v) > self.max_string_length:
                        elem[k] = f'{v[:self.max_string_length - 15]}... (TRUNCATED)'[:self.max_string_length]
            if isinstance(elem, list):
                for i, item in enumerate(elem):
                    elem[i] = f'{item[:self.max_string_length - 15]}... (TRUNCATED)'[:self.max_string_length]

        return json.dumps(safe_log_data,
                          ensure_ascii=self.ensure_ascii,
                          allow_nan=self.allow_nan,
                          indent=self.indent,
                          separators=self.separators,
                          sort_keys=self.sort_keys)
