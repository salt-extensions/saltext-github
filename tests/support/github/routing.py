"""
Route declaration plumbing for the fake GitHub API.
"""

import re
from typing import Any
from typing import Literal
from typing import NamedTuple
from typing import TypeAlias

HTTP_METHOD: TypeAlias = Literal[  # pylint: disable=invalid-name
    "GET", "POST", "PUT", "PATCH", "DELETE"
]


class Request(NamedTuple):
    method: HTTP_METHOD
    path: str
    query: dict[str, Any]
    body: Any


def _route(method, *specs):
    """
    Mark a route-mixin method as the handler for an API route.

    Specs are either full regexes (detected via an explicit ``(?P<`` group)
    or shorthand paths whose ``<name>`` segments are expanded into named
    groups: ``\\d+`` for names ending in ``_id``/``number``, ``[^/]+``
    otherwise. A leading slash is optional in shorthand specs.
    """

    def decorator(func):
        patterns = []
        for spec in specs:
            if "(?P<" in spec:
                # Already a full regex
                patterns.append(spec)
                continue
            rend = []
            for sgmnt in spec.lstrip("/").split("/"):
                if sgmnt.startswith("<") and sgmnt.endswith(">"):
                    sgmnt = (
                        rf"(?P{sgmnt}\d+)"
                        if sgmnt.endswith(("_id>", "number>"))
                        else rf"(?P{sgmnt}[^/]+)"
                    )
                rend.append(sgmnt)
            patterns.append("/" + "/".join(rend))
        func.routes = (method, tuple(re.compile(ptrn) for ptrn in patterns))
        return func

    return decorator


def GET(*specs):  # pylint: disable=invalid-name
    return _route("GET", *specs)


def POST(*specs):  # pylint: disable=invalid-name
    return _route("POST", *specs)


def PUT(*specs):  # pylint: disable=invalid-name
    return _route("PUT", *specs)


def PATCH(*specs):  # pylint: disable=invalid-name
    return _route("PATCH", *specs)


def DELETE(*specs):  # pylint: disable=invalid-name
    return _route("DELETE", *specs)
