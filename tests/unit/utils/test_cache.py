import pytest
import salt.cache

from saltext.github.utils.gh import cache as gh_cache

PUSHED = "2026-10-14T12:00:00+00:00"


class FakeSaltCache:
    def __init__(self):
        self.data = {}
        self.fail = False

    def _check(self):
        if self.fail:
            raise OSError("disk on fire")

    def fetch(self, bank, key):
        self._check()
        return self.data.get((bank, key), {})

    def store(self, bank, key, value):
        self._check()
        self.data[(bank, key)] = value

    def flush(self, bank, key=None):
        self._check()
        self.data.pop((bank, key), None)


@pytest.fixture
def backend(monkeypatch):
    fake = FakeSaltCache()
    monkeypatch.setattr(salt.cache, "factory", lambda opts: fake)
    return fake


@pytest.fixture
def store(backend):  # pylint: disable=unused-argument
    return gh_cache.PersistentCache({}, "ident123")


def test_meta_roundtrip(store):
    assert store.get_meta("auth_login") is gh_cache.MISS
    store.set_meta("auth_login", "user1")
    assert store.get_meta("auth_login") == "user1"


def test_meta_none_value_is_not_a_miss(store):
    store.set_meta("something", None)
    assert store.get_meta("something") is None


def test_file_roundtrip(store):
    assert store.get_file("Org", "Repo", "a.yml", PUSHED) is gh_cache.MISS
    store.set_file("Org", "Repo", "a.yml", "content", PUSHED)
    # Owner/repo lookups are case-insensitive, paths are not
    assert store.get_file("org", "repo", "a.yml", PUSHED) == "content"
    assert store.get_file("org", "repo", "A.yml", PUSHED) is gh_cache.MISS


def test_file_negative_content_is_not_a_miss(store):
    store.set_file("org", "repo", "missing.yml", None, PUSHED)
    assert store.get_file("org", "repo", "missing.yml", PUSHED) is None


def test_file_pushed_at_mismatch_is_a_miss(store):
    store.set_file("org", "repo", "a.yml", "content", PUSHED)
    assert store.get_file("org", "repo", "a.yml", "2026-10-15T00:00:00+00:00") is gh_cache.MISS


def test_file_new_pushed_at_discards_stale_siblings(store):
    store.set_file("org", "repo", "a.yml", "old-a", PUSHED)
    newer = "2026-10-15T00:00:00+00:00"
    store.set_file("org", "repo", "b.yml", "new-b", newer)
    assert store.get_file("org", "repo", "b.yml", newer) == "new-b"
    # a.yml was stored for the old pushed_at and must not survive
    assert store.get_file("org", "repo", "a.yml", newer) is gh_cache.MISS
    assert store.get_file("org", "repo", "a.yml", PUSHED) is gh_cache.MISS


def test_file_unknown_pushed_at_disables(store, backend):
    assert store.get_file("org", "repo", "a.yml", None) is gh_cache.MISS
    store.set_file("org", "repo", "a.yml", "content", None)
    assert not backend.data


def test_flush_repo(store):
    store.set_file("org", "repo", "a.yml", "content", PUSHED)
    store.set_file("org", "other", "a.yml", "other", PUSHED)
    store.flush_repo("ORG", "Repo")
    assert store.get_file("org", "repo", "a.yml", PUSHED) is gh_cache.MISS
    assert store.get_file("org", "other", "a.yml", PUSHED) == "other"


@pytest.mark.usefixtures("backend")
def test_ident_namespacing():
    one = gh_cache.PersistentCache({}, "ident1")
    two = gh_cache.PersistentCache({}, "ident2")
    one.set_meta("auth_login", "user1")
    assert two.get_meta("auth_login") is gh_cache.MISS


def test_backend_errors_degrade_to_misses(store, backend, caplog):
    store.set_file("org", "repo", "a.yml", "content", PUSHED)
    backend.fail = True
    with caplog.at_level("WARNING"):
        assert store.get_file("org", "repo", "a.yml", PUSHED) is gh_cache.MISS
        assert store.get_meta("auth_login") is gh_cache.MISS
        store.set_meta("auth_login", "user1")  # must not raise
        store.set_file("org", "repo", "b.yml", "x", PUSHED)  # must not raise
        store.flush_repo("org", "repo")  # must not raise
    assert "persistent GitHub cache" in caplog.text
