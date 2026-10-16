"""
Tests for the persistent connection cache (the ``cache`` profile
parameter, enabled by default).

The shared test profile opts out for test isolation; this module
removes the key again, exercising the on-by-default behavior, and
flushes the cache between tests itself.

Fresh loader contexts simulate separate processes (as with
``salt-call --local``, where in-memory caches never survive): only the
persistent cache in the minion's ``cachedir`` carries over.
"""

import copy
import os
import shutil

import pytest
import salt.loader

from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh.cache import CACHE_ROOT

GRAINS_FILES = {
    "copier": {
        "path": ".copier-answers.yml",
        "exclude": ["_*"],
    },
}


@pytest.fixture(scope="module")
def resource_decl():
    return {"profile": "github", "grains_files": GRAINS_FILES}


@pytest.fixture(scope="module")
def res_opts(minion_opts, resource_decl):
    opts = copy.deepcopy(minion_opts)
    # Drop the shared test profile's opt-out to exercise the
    # on-by-default behavior
    opts["github"].pop("cache", None)
    opts["pillar"] = {"resources": {"github": resource_decl}}
    return opts


@pytest.fixture(autouse=True)
def _flush_persistent_cache(res_opts):
    """
    The persistent cache outlives the per-test fake state reset by
    design — isolate the tests.
    """
    try:
        yield
    finally:
        shutil.rmtree(os.path.join(res_opts["cachedir"], CACHE_ROOT), ignore_errors=True)


@pytest.fixture
def cold_funcs(res_opts, utils_loader):
    """
    Factory for resource loaders with a fresh context, simulating a new
    process.
    """
    counter = iter(range(100))

    def _build(opts=None):
        funcs = salt.loader.resource(
            opts or res_opts,
            utils=utils_loader,
            context={},
            loaded_base_name=f"{__name__}.cold{next(counter)}",
        )
        funcs["github.init"](opts or res_opts)
        return funcs

    return _build


def _contents_requests(fake_github):
    return len(fake_github.filter_requests(path="*/contents/*"))


def test_file_fetches_persist_across_processes(cold_funcs, for_resource, fake_github):
    with for_resource("testorg/repo-a"):
        grains = cold_funcs()["github.grains"]()
    assert grains["copier"]["team"] == "platform"
    assert _contents_requests(fake_github) == 1
    with for_resource("testorg/repo-a"):
        grains = cold_funcs()["github.grains"]()
    assert grains["copier"]["team"] == "platform"
    # Served from the persistent cache: no new contents request
    assert _contents_requests(fake_github) == 1


def test_negative_fetches_persist_across_processes(cold_funcs, for_resource, fake_github):
    # repo-b does not carry the declared file
    with for_resource("testorg/repo-b"):
        grains = cold_funcs()["github.grains"]()
    assert "copier" not in grains
    assert _contents_requests(fake_github) == 1
    with for_resource("testorg/repo-b"):
        cold_funcs()["github.grains"]()
    assert _contents_requests(fake_github) == 1


def test_push_invalidates(cold_funcs, for_resource, fake_github, fake_org):
    with for_resource("testorg/repo-a"):
        cold_funcs()["github.grains"]()
    repo = fake_org.get_repo("repo-a")
    repo.get_file(".copier-answers.yml").update(content="team: pushed")
    repo.update(pushed_at="2026-10-15T00:00:00Z")
    with for_resource("testorg/repo-a"):
        grains = cold_funcs()["github.grains"]()
    assert grains["copier"] == {"team": "pushed"}
    assert _contents_requests(fake_github) == 2


def test_stale_without_push(cold_funcs, for_resource, fake_github, fake_org):
    """
    Cache entries are valid until the repository's ``pushed_at``
    changes — content changes without a push (impossible on real
    GitHub) are not detected.
    """
    with for_resource("testorg/repo-a"):
        cold_funcs()["github.grains"]()
    fake_org.get_repo("repo-a").get_file(".copier-answers.yml").update(content="team: changed")
    with for_resource("testorg/repo-a"):
        grains = cold_funcs()["github.grains"]()
    assert grains["copier"]["team"] == "platform"
    assert _contents_requests(fake_github) == 1


def test_grains_refresh_bypasses_and_rewrites(cold_funcs, for_resource, fake_github, fake_org):
    with for_resource("testorg/repo-a"):
        cold_funcs()["github.grains"]()
    fake_org.get_repo("repo-a").get_file(".copier-answers.yml").update(content="team: changed")
    with for_resource("testorg/repo-a"):
        refreshed = cold_funcs()["github.grains_refresh"]()
    assert refreshed["copier"]["team"] == "changed"
    fetched = _contents_requests(fake_github)
    assert fetched == 2
    # The refresh rewrote the persistent entry: a new process serves it
    with for_resource("testorg/repo-a"):
        grains = cold_funcs()["github.grains"]()
    assert grains["copier"]["team"] == "changed"
    assert _contents_requests(fake_github) == fetched


def test_owner_type_persists_across_processes(cold_funcs, res_opts, fake_github):
    cold_funcs()["github.discover"](res_opts)
    assert len(fake_github.filter_requests(path="/users/testorg")) == 1
    cold_funcs()["github.discover"](res_opts)
    # The account type lookup is served from the persistent cache
    assert len(fake_github.filter_requests(path="/users/testorg")) == 1


def test_auth_login_persists_across_processes(cold_funcs, res_opts, github_profile, fake_github):
    """
    With an ownerless profile, the default owner is the token's user,
    whose login lookup (GET /user) persists across processes.
    """
    opts = copy.deepcopy(res_opts)
    opts["github"] = {"token": github_profile["token"], "api_url": github_profile["api_url"]}
    assert cold_funcs(opts)["github.discover"](opts) == ["user1/repo-a", "user1/user-repo"]
    assert len(fake_github.filter_requests(path="/user")) == 1
    assert cold_funcs(opts)["github.discover"](opts) == ["user1/repo-a", "user1/user-repo"]
    assert len(fake_github.filter_requests(path="/user")) == 1


def test_identity_persists_for_classic_invocations(res_opts, fake_github):
    """
    The cache is a profile-level feature: connections resolved outside
    the resource subsystem persist token/account identities as well.
    """
    conn = gh_profile.get_conn("github", opts=res_opts, context={})
    assert conn.owner_type("user1") == "User"
    assert len(fake_github.filter_requests(path="/users/user1")) == 1
    conn = gh_profile.get_conn("github", opts=res_opts, context={})
    assert conn.owner_type("user1") == "User"
    assert len(fake_github.filter_requests(path="/users/user1")) == 1


def test_cache_disabled_via_profile(cold_funcs, res_opts, for_resource, fake_github):
    opts = copy.deepcopy(res_opts)
    opts["github"]["cache"] = False
    with for_resource("testorg/repo-a"):
        cold_funcs(opts)["github.grains"]()
        cold_funcs(opts)["github.grains"]()
    # Without the persistent cache, each fresh process refetches
    assert _contents_requests(fake_github) == 2
