import getpass
import os
import platform
import socket
from functools import lru_cache
from pathlib import Path
from typing import Optional

__version__: str = '0.3'


@lru_cache
def get_service_name() -> str:
    """
    get something useful as a service name of whatever's currently running
    what makes a good service name is not really well specified
    and services are usually both clients and servers at the same time, often both in the same trace
    hence i've decided to return something that should uniquely represent the current running instance

    todo: maybe include the py file that's being run as __main__ instead of the user?

    :return: {username}@{hostname}.{namespace or domain}
    """

    # get username
    username = getpass.getuser().strip() or None

    # get hostname
    hostname: str = (os.getenv('HOSTNAME', '').strip() or
                     os.getenv('COMPUTERNAME', '').strip() or
                     (socket.gethostname() or '').strip() or
                     (platform.node() or '').strip() or
                     '<UNKNOWN>')

    # get k8s namespace
    # https://kubernetes.io/docs/tasks/run-application/access-api-from-pod/#directly-accessing-the-rest-api
    namespace_path = Path('/var/run/secrets/kubernetes.io/serviceaccount/namespace')
    if namespace_path.is_file():
        namespace = namespace_path.read_text().strip() or None

    # not in k8s, get domain or something
    else:
        namespace = None

        # try to strip hostname out of fqdn
        fqdn = socket.getfqdn()
        if fqdn.strip().casefold().startswith(f'{hostname.casefold()}.'):
            namespace = fqdn[len(hostname.casefold()) + 1:].strip() or None

        # otherwise try to get windows userdomain
        if namespace is None:
            namespace = os.getenv('USERDOMAIN', '').strip() or None
            if namespace.casefold() == hostname.casefold():
                namespace = None

    # formatting
    _username = f'{username}@' if username else ''
    _namespace = f'.{namespace}' if namespace else ''
    return f'{_username}{hostname}{_namespace}'


__service_name__: Optional[str] = get_service_name()
