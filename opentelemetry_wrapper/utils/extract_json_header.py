import base64
import binascii
import json
from functools import lru_cache
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union


def extract_json_header(header_value: Optional[str]) -> Optional[Dict[str, Union[bool, str, int, float]]]:
    """
    extract JSON as a flat dict from a (possibly base64-encoded) string

    :param header_value:
    :return:
    """
    # does not extract keys where the value is None
    try:
        # only strings can be decoded
        if not isinstance(header_value, str):
            return None

        # userinfo detection and handling
        if header_value.startswith('ey'):  # likely base-64 encoded json, decoded string starts with "{
            # todo: test other fast filters for JWT-like content
            # '.ey' in header_value
            # '.' in set(header_value)
            # [use a predefined set] set('.').issubset(set(header_value))
            # [use a predefined set] set(header_value).issubset(set(base64_chars))
            # [use a precompiled regex] re.compile(r'\.').search(header_value)
            if '.' in header_value:
                return None  # probably a JWT
            _header_value = header_value.rstrip('=')
            if _header_value[-1] in {'Q', '0', '9'}:  # decoded string ends with "}"
                return _extract_userinfo(_header_value)

        # json handling
        if header_value.startswith('{') and header_value.endswith('}'):
            return _flatten_json(json.loads(header_value))
        if header_value.startswith('[') and header_value.endswith(']'):
            return _flatten_json(json.loads(header_value))

    except Exception:
        pass

    # didn't extract anything
    return None


@lru_cache(maxsize=0x10000)
def _extract_userinfo(header_value: str) -> Optional[Dict[str, Union[bool, str, int, float]]]:
    """
    extract the oauth userinfo token into a flat dict
    if the provided value is not base64-encoded json, returns None

    this function is cached because the userinfo token (almost) never changes
    since the userinfo token is injected by the api gateway there shouldn't be cache-busting dos attacks

    :param header_value:
    :return:
    """
    # cache userinfo tokens since they usually don't change
    try:
        # already stripped trailing "=" buffer chars before passing in the data
        _header_value = json.loads(base64.b64decode(header_value.rstrip('=') + '==', validate=True))
    except binascii.Error:
        return None
    except UnicodeDecodeError:
        return None
    except json.decoder.JSONDecodeError:
        return None

    return _flatten_json(_header_value)


def _flatten_json(header_value: Union[Dict, List, bool, str, int, float, None],
                  ) -> Dict[str, Union[bool, str, int, float]]:
    """
        parses a json string and flattens it into an un-nested dictionary, dropping null values
        >>> _flatten_json({'a': {'aa': {'aaa': 'AAA'}, 'x': None}, 'b': [1, 2, 3]})
        {'a.aa.aaa': 'AAA', 'b.[0]': 1, 'b.[1]': 2, 'b.[2]': 3}
        >>> _flatten_json(['x', None, {1: 11, 2: 22}, 'y'])
        {'[0]': 'x', '[2].1': 11, '[2].2': 22, '[3]': 'y'}

        if you pass in a string or number, it returns a dictionary with a single key, which will be an empty string
        >>> _flatten_json('asdf')
        {'': 'asdf'}
        >>> _flatten_json(1234)
        {'': 1234}
        >>> _flatten_json(12.34)
        {'': 12.34}

        if you pass in a null, it returns an empty dictionary
        >>> _flatten_json(None)
        {}

        unhandled edge case: if you pass in a dict with a key containing a full stop, it looks like a nested dict
        >>> _flatten_json({'a.b': 123})
        {'a.b': 123}
        >>> _flatten_json({'a': {'b': 123}})
        {'a.b': 123}

        unhandled edge case: if you pass in a dict with a numeric key wrapped in square brackets, it looks like a list
        >>> _flatten_json({'[0]': 'a', '[1]': 'b'})
        {'[0]': 'a', '[1]': 'b'}
        >>> _flatten_json(['a', 'b'])
        {'[0]': 'a', '[1]': 'b'}

        :param header_value:
        :return:
        """
    out = dict()
    stack: List[Tuple[str, Union[bool, str, int, float, dict, list, None]]]
    stack = [('', header_value)]
    while stack:
        node_name, node = stack.pop()
        if isinstance(node, dict):
            for k, v in reversed(node.items()):  # reversed because we're on a stack
                stack.append((f'{node_name}.{k}' if node_name else k, v))
        elif isinstance(node, list):
            for k, v in reversed(list(enumerate(node))):  # reversed because we're on a stack
                stack.append((f'{node_name}.[{k}]' if node_name else f'[{k}]', v))
        elif isinstance(node, (bool, str, int, float)):  # exclude None
            out[node_name] = node
    return out


if __name__ == '__main__':
    some_object = {'a': {'aa': {'aaa': 'AAA'}, 'x': None}, 'b': 2}
    print(extract_json_header(json.dumps(some_object)))
    userinfo_string = base64.b64encode(json.dumps(some_object).encode('ascii')).decode('ascii').rstrip('=')
    print(userinfo_string)
    print(_extract_userinfo(userinfo_string))
