"""
Request dispatch, shared route helpers and HTTP plumbing of the fake GitHub API.
"""

import fnmatch
import json
import re
import threading
import traceback
from collections.abc import Callable
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs
from urllib.parse import unquote
from urllib.parse import urlsplit

from nacl.public import PrivateKey

from tests.support.github.entities import Organization
from tests.support.github.entities import Repo
from tests.support.github.routing import HTTP_METHOD
from tests.support.github.routing import Request
from tests.support.github.state import GlobalState

TOKEN = "test-token"
ORG = "testorg"

# Sample SSH public keys for deploy key tests
DEPLOY_KEY_A = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPDeployKeyAForTesting0000000000000000000A existing"
)
DEPLOY_KEY_B = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPDeployKeyBForTesting0000000000000000000B replacement"
)


class APIBase:
    """
    Request dispatch and shared helpers. Routes are contributed by the
    mixin classes in :mod:`tests.support.github.routes` and discovered
    via the MRO on instantiation.
    """

    def __init__(self, token: str = TOKEN, state: GlobalState | None = None):
        self.token = token
        self.base_url = None
        self.lock = threading.Lock()
        self.requests = []
        self.state = state or GlobalState()
        # Keypair for the Actions secrets sealed-box encryption
        self.secrets_private_key = PrivateKey.generate()
        self._server = None
        self._routes: dict[HTTP_METHOD, list[tuple[tuple[re.Pattern[str], ...], Callable]]] = {}
        for name in dir(self):
            if (routes := getattr(func := getattr(self, name), "routes", None)) is not None:
                self._routes.setdefault(routes[0], []).append((routes[1], func))

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset(self):
        """
        Restore the seeded state and clear the request log.
        """
        with self.lock:
            self.requests = []
            self.state.restore()

    # ------------------------------------------------------------------
    # Shared route helpers
    # ------------------------------------------------------------------

    def _resolve_org(self, match: re.Match | dict[str, str]) -> Organization:
        if isinstance(match, re.Match):
            groups = match.groupdict()
        else:
            groups = match
        if (org := groups.get("org")) is not None:
            func, identifier = self.state.get_org, org
        elif (org_id := groups.get("org_id")) is not None:
            func, identifier = self.state.get_org_id, org_id
        else:
            raise TypeError(f"no org or org_id specified: {groups}")  # pragma: no cover
        return func(identifier)

    def _resolve_repo(self, match: re.Match | dict[str, str]) -> Repo:
        if isinstance(match, re.Match):
            groups = match.groupdict()
        else:
            groups = match
        if "repo" not in groups:
            raise TypeError(f"no repo specified: {groups}")  # pragma: no cover
        org = self._resolve_org(groups)
        return org.get_repo(groups["repo"])

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, method, path, query, body, auth):
        """
        Route a request. Returns ``(status, headers, payload)``.
        """
        with self.lock:
            self.requests.append(Request(method, path, query, body))
            if auth not in (f"token {self.token}", f"Bearer {self.token}"):  # pragma: no cover
                return 401, {}, {"message": "Bad credentials"}
            for patterns, func in self._routes.get(method, ()):
                for route in patterns:
                    if match := route.fullmatch(path):
                        break
                else:
                    continue
                try:
                    return self._chunk(query, path, self._normalize(func(match, query, body)))
                except KeyError as err:
                    return (
                        404,
                        {},
                        {"message": f"Not Found: {err}\n\n{traceback.format_exception(err)}"},
                    )
                except Exception as err:  # pylint: disable=broad-except  # pragma: no cover
                    return (
                        422,
                        {},
                        {
                            "message": f"Fake server error: {err!r}\n\n{traceback.format_exception(err)}"
                        },
                    )
            return (  # pragma: no cover
                404,
                {},
                {"message": f"Not Found: no route for {method} {path}"},
            )

    @staticmethod
    def _normalize(result):
        if isinstance(result, int):
            return result, {}, None
        if len(result) == 2:
            status, payload = result
            return status, {}, payload
        return result

    def _chunk(self, query, path, result):
        status, headers, body = result
        if "per_page" not in query or status >= 400 or not isinstance(body, list):
            return result
        status, headers, body = result
        per_page = int(query["per_page"])
        page = int(query.get("page", 1))
        start = (page - 1) * per_page
        chunk = body[start : start + per_page]
        if start + per_page < len(body):
            headers["Link"] = (
                f"<{self.base_url}{path}?per_page={per_page}&page={page + 1}>; " f'rel="next"'
            )
        elif page > 1:
            # Like the real API, later pages always carry a Link header,
            # even when there is no next page.
            headers["Link"] = (
                f"<{self.base_url}{path}?per_page={per_page}&page={page - 1}>; " f'rel="prev"'
            )
        return status, headers, chunk

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def filter_requests(self, method=None, path=None, query=None):
        """
        Return all logged requests that match a spec.

        method
            (List of) HTTP methods to filter logged requests for.

        path
            (List of) fnmatch-style globs to filter logged requests for.

        query
            (List of) query keys to filter logged requests for.
        """
        ret = self.requests
        if method is not None:
            methods = (
                [method.upper()] if isinstance(method, str) else [meth.upper() for meth in method]
            )
            ret = [req for req in ret if req.method in methods]
        if path is not None:
            paths = [path] if isinstance(path, str) else path
            ret = [req for req in ret if any(fnmatch.fnmatch(req.path, ptrn) for ptrn in paths)]
        if query is not None:
            queries = [query] if isinstance(query, str) else query
            ret = [req for req in ret if any(qry in req.query for qry in queries)]
        return ret

    def mutations(self):
        """
        Return all logged non-GET requests, for asserting test-mode behavior.
        """
        return [req for req in self.requests if req.method != "GET"]

    # ------------------------------------------------------------------
    # HTTP server plumbing
    # ------------------------------------------------------------------

    @contextmanager
    def serve(self):
        """
        Run the server on an ephemeral localhost port.
        """
        api = self

        class _Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                body = json.loads(raw) if raw else None
                split = urlsplit(self.path)
                query = {key: vals[0] for key, vals in parse_qs(split.query).items()}
                status, headers, payload = api.dispatch(
                    self.command,
                    unquote(split.path),
                    query,
                    body,
                    self.headers.get("Authorization"),
                )
                data = b"" if payload is None else json.dumps(payload).encode()
                self.send_response(status)
                for key, val in headers.items():
                    self.send_header(key, val)
                if data:
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if data:
                    self.wfile.write(data)

            do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = _handle

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        server.daemon_threads = True
        self._server = server
        self.base_url = self.state.base_url = f"http://127.0.0.1:{server.server_address[1]}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield self
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    @property
    def url(self):
        return self.base_url
