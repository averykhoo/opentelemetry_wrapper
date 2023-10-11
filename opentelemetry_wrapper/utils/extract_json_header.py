import base64
import binascii
import json
from functools import lru_cache
from typing import Dict
from typing import Optional
from typing import Union


def extract_json_header(header_value: str) -> Optional[Dict[str, Union[bool, str, bytes, int, float]]]:
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
            # [use a precompiled regex] re.compile(r'\.').match(header_value)
            if '.' in header_value:
                return None  # probably a JWT
            _header_value = header_value.rstrip('=')
            if _header_value[-1] in {'Q', '0', '9'}:  # decoded string ends with "}"
                return _extract_userinfo(_header_value)

        # json handling
        if header_value.startswith('{') and header_value.endswith('}'):
            return _extract_json(header_value)
        if header_value.startswith('[') and header_value.endswith(']'):
            return _extract_json(header_value)

    except Exception:
        pass

    # didn't extract anything
    return None


@lru_cache(maxsize=0xFF)
def _extract_userinfo(header_value: str) -> Optional[Dict[str, Union[bool, str, bytes, int, float]]]:
    # cache userinfo tokens since they usually don't change
    try:
        # already stripped trailing "=" buffer chars before passing in the data
        _header_value = base64.b64decode(header_value + '==', validate=True)
    except binascii.Error:
        return None

    return _extract_json(_header_value)


def _extract_json(header_value: Union[str, bytes]) -> Optional[Dict[str, Union[bool, str, bytes, int, float]]]:
    out = dict()
    stack = [(None, json.loads(header_value))]
    while stack:
        node_name, node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                child_node_name = f'{node_name}.{k}' if node_name else k
                if isinstance(v, (bool, str, bytes, int, float)):  # exclude None
                    out[child_node_name] = v
                elif isinstance(v, (dict, list)):
                    stack.append((child_node_name, v))
        elif isinstance(node, list):
            for k, v in enumerate(node):
                child_node_name = f'{node_name}.[{k}]' if node_name else f'[{k}]'
                if isinstance(v, (bool, str, bytes, int, float)):  # exclude None
                    out[child_node_name] = v
                elif isinstance(v, (dict, list)):
                    stack.append((child_node_name, v))

    return out


if __name__ == '__main__':
    print(extract_json_header(json.dumps({'a': {'aa': {'aaa': 'AAA'}, 'x': None}, 'b': 2})))
