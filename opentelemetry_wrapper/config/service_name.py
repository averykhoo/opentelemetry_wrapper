# noinspection PyPackageRequirements
import __main__  # technically we only need __main__.__file__
import getpass
import os
import platform
import socket
from functools import lru_cache
from pathlib import Path

from opentelemetry.sdk.resources import OTELResourceDetector


@lru_cache
def get_username() -> str:
    # noinspection PyBroadException
    try:
        return getpass.getuser().strip()
    except Exception:
        return ''


@lru_cache
def get_hostname() -> str:
    out = ''
    if not out:
        out = os.getenv('HOSTNAME', '').strip()  # linux
    if not out:
        out = os.getenv('COMPUTERNAME', '').strip()  # windows
    if not out:
        # noinspection PyBroadException
        try:
            out = platform.node().strip()
        except Exception:
            pass
    if not out:
        # noinspection PyBroadException
        try:
            out = socket.gethostname().strip()
        except Exception:
            pass
    return out


@lru_cache
def get_namespace() -> str:
    # get k8s namespace
    # https://kubernetes.io/docs/tasks/run-application/access-api-from-pod/#directly-accessing-the-rest-api
    namespace_path = Path('/var/run/secrets/kubernetes.io/serviceaccount/namespace')
    if namespace_path.is_file():
        # noinspection PyBroadException
        try:
            namespace = namespace_path.read_text().strip()
            if namespace:
                return namespace
        except Exception:
            pass

    # not in k8s, try to get domain by removing hostname from fqdn
    hostname = get_hostname()
    # noinspection PyBroadException
    try:
        fqdn = socket.getfqdn()
        if fqdn.strip().casefold().startswith(f'{hostname.casefold()}.'):
            return fqdn[len(hostname) + 1:].strip()
    except Exception:
        pass

    # otherwise try to get windows userdomain
    out = ''
    if not out:
        out = os.getenv('USERDNSDOMAIN', '').strip()
    if not out:
        out = os.getenv('USERDOMAIN', '').strip()
    if out and out.casefold() != hostname.casefold():
        return out

    # todo: also try getting the primary dns suffix from the dns suffix search list

    # everything failed, return nothing
    return ''


@lru_cache
def get_main_filename() -> str:
    if getattr(__main__, '__file__', None):
        main_full_path = Path(__main__.__file__)  # can be undefined, e.g. C modules or Jupyter notebooks
        if main_full_path.is_file():  # should always be true
            return main_full_path.name

    return ''


@lru_cache
def get_default_service_name() -> str:
    """
    get something useful as a service name of whatever's currently running
    what makes a good service name is not really well specified
    and services are usually both clients and servers at the same time, often both in the same trace

    note that this does not follow the opentelemetry spec for `service.name`, which is here:
    https://opentelemetry.io/docs/reference/specification/resource/semantic_conventions/#service
    because this tries to uniquely represent the current running instance

    it would be more correct to just return the namespace instead,
    but my preference (for now at least) is to isolate the instance for further debugging

    :return: {username}@{hostname}.{namespace or domain}:<{filename of main}> or an empty string
    """

    # formatting
    _username = f'{get_username()}@' if get_username() else ''
    _hostname = get_hostname()
    _namespace = f'.{get_namespace()}' if get_namespace() else ''
    _filename = f':<{get_main_filename()}>' if get_main_filename() else ''

    # if at least one of the above succeeded, then make sure hostname is not blank
    # _hostname = _hostname if _hostname or not (_username or _namespace or _filename) else '<UNKNOWN_HOST>'
    if not _hostname:
        if _username or _namespace or _filename:
            _hostname = '<UNKNOWN_HOST>'

    # format the output nicely
    return f'{_username}{_hostname}{_namespace}{_filename}'


def getenv_otel_service_name() -> str:
    """
    tries these 3 things, in order:
    1. `OTEL_SERVICE_NAME` env var
    2. `service.name` property from `OTEL_RESOURCE_ATTRIBUTES` env var
    3. `get_default_service_name()` (which technically breaks OpenTelemetry spec)
    if all the above fails, falls back to 'unknown_service'
    """
    otel_detected_service_name = OTELResourceDetector().detect().attributes.get('service.name', '') or ''
    return str(otel_detected_service_name).strip()
