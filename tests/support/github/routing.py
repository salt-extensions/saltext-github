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
    """

    def decorator(func):
        patterns = []
        for spec in specs:
            if not spec[0].islower():
                # Implicitly treat leading [a-z] as "generate a pattern". This is already one.
                patterns.append(spec)
                continue
            rend = []
            for sgmnt in spec.split("/"):
                if sgmnt.startswith("<") and sgmnt.endswith(">"):
                    sgmnt = rf"(?P{sgmnt}\d+)" if sgmnt.endswith("_id>") else rf"(?P{sgmnt}[^/]+)"
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
