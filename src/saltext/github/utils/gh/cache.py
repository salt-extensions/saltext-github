"""
Optional persistent cross-process cache for slow-changing GitHub API
data, backed by the minion's :py:mod:`salt.cache` (``cachedir``).

Attached to every profile-resolved
:class:`~saltext.github.utils.gh.client.GitHubConnection` as its
``store`` unless the profile opts out via :ghconf:`cache`. Particularly
useful for ``salt-call --local`` setups, where every invocation starts
a fresh process and the in-memory caches never survive.

Two kinds of data are stored, namespaced by a token/API URL-derived
identity so rotated credentials or different endpoints never share
entries:

* Repository file contents (fetched for
  :ghconf:`resource:grains_files`), validated against the repository's
  ``pushed_at`` timestamp – entries are served until the repository
  receives a new push. Negative lookups (missing files) are cached the
  same way.
* Metadata that is stable for a given token/owner: account types
  (organization vs user) and the token's user login. These are stored
  indefinitely.

All storage errors degrade gracefully to cache misses.
"""

import logging

log = logging.getLogger(__name__)

CACHE_ROOT = "saltext_github"
#: Sentinel for missing cache entries (``None`` is a valid cached value).
MISS = object()


class PersistentCache:
    """
    ``salt.cache``-backed store, see the module docstring.

    opts
        The minion configuration (``__opts__``), selecting the cache
        backend and ``cachedir``.

    ident
        Identity string namespacing all entries, derived from the
        connection's token and API URL
        (:attr:`~saltext.github.utils.gh.client.GitHubConnection.ident`).
    """

    def __init__(self, opts, ident):
        # Local import: salt.cache pulls in the loader machinery, which
        # not all importers of this package need.
        import salt.cache  # pylint: disable=import-outside-toplevel

        self._cache = salt.cache.factory(opts)
        self._base = f"{CACHE_ROOT}/{ident}"

    def _fetch(self, bank, key):
        try:
            return self._cache.fetch(f"{self._base}/{bank}", key)
        except Exception as err:  # pylint: disable=broad-except
            log.warning("Failed reading from the persistent GitHub cache: %s", err)
            return None

    def _store(self, bank, key, value):
        try:
            self._cache.store(f"{self._base}/{bank}", key, value)
        except Exception as err:  # pylint: disable=broad-except
            log.warning("Failed writing to the persistent GitHub cache: %s", err)

    def get_meta(self, key):
        """
        Return a stored metadata value, or :data:`MISS`.
        """
        data = self._fetch("meta", key)
        if isinstance(data, dict) and "value" in data:
            return data["value"]
        return MISS

    def set_meta(self, key, value):
        """
        Store a metadata value.
        """
        self._store("meta", key, {"value": value})

    def get_file(self, owner, repo, path, pushed_at):
        """
        Return a repository file's stored content (which is ``None`` for
        cached negative lookups), or :data:`MISS` when there is no entry
        or the stored entry does not match ``pushed_at``.
        """
        if not pushed_at:
            return MISS
        entry = self._fetch(f"files/{owner.lower()}", repo.lower())
        if (
            isinstance(entry, dict)
            and entry.get("pushed_at") == pushed_at
            and path in entry.get("files", {})
        ):
            return entry["files"][path]
        return MISS

    def set_file(self, owner, repo, path, content, pushed_at):
        """
        Store a repository file's content (``None`` for a negative
        lookup) under the repository's current ``pushed_at``. Entries
        stored for a different ``pushed_at`` are discarded.
        """
        if not pushed_at:
            return
        bank = f"files/{owner.lower()}"
        key = repo.lower()
        entry = self._fetch(bank, key)
        if not isinstance(entry, dict) or entry.get("pushed_at") != pushed_at:
            entry = {"pushed_at": pushed_at, "files": {}}
        entry["files"][path] = content
        self._store(bank, key, entry)

    def flush_repo(self, owner, repo):
        """
        Drop all stored file contents of one repository.
        """
        try:
            self._cache.flush(f"{self._base}/files/{owner.lower()}", repo.lower())
        except Exception as err:  # pylint: disable=broad-except
            log.warning("Failed flushing the persistent GitHub cache: %s", err)
