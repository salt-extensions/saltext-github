"""
Verify native GitHub App authentication: profiles carrying ``app_id`` +
``private_key`` mint installation tokens via a signed JWT, discover the
app's installation on the profile's ``owner`` (unless pinned via
``installation_id``) and derive a token-independent connection identity.
"""

import copy
import os
import shutil
from datetime import timedelta

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh.cache import CACHE_ROOT
from saltext.github.utils.gh.client import get_app_connection_ident
from saltext.github.utils.gh.client import revoke_installation_token
from saltext.github.utils.gh.exceptions import GitHubApiError
from tests.support.github import APP_INSTALLATION_ID
from tests.support.github import TOKEN


@pytest.fixture(scope="module")
def minion_config_defaults(fake_github):
    app_profile = {
        "app_id": fake_github.app_id,
        "private_key": fake_github.app_private_key,
        "api_url": fake_github.url,
        "owner": "testorg",
        "repo_name": "repo-a",
        "cache": False,
    }
    return {
        "github": app_profile,
        "github_inst": {**app_profile, "installation_id": APP_INSTALLATION_ID},
        "github_user": {**app_profile, "owner": "user1"},
        "github_noowner": {key: val for key, val in app_profile.items() if key != "owner"},
        # otherorg exists, but the app is not installed on it
        "github_badowner": {**app_profile, "owner": "otherorg"},
        "github_scoped": {**app_profile, "permissions": {"contents": "read", "metadata": "read"}},
        "github_pat": {
            "token": TOKEN,
            "api_url": fake_github.url,
            "owner": "testorg",
            "cache": False,
        },
    }


def _discovery_requests(fake_github):
    return [req.path for req in fake_github.filter_requests(path="*/installation")]


def test_org_operations(github_repo, fake_org, fake_github):
    assert github_repo.info()["full_name"] == "testorg/repo-a"
    assert set(github_repo.list()) == {"repo-a", "repo-b"}
    assert github_repo.create("app-created")["full_name"] == "testorg/app-created"
    assert "app-created" in fake_org.repos
    # The installation token was minted via the JWT-authenticated app endpoint
    assert fake_github.filter_requests(path="/app/installations/*/access_tokens")
    # The installation was discovered from the profile's owner, once per
    # context (the connection is reused)
    assert _discovery_requests(fake_github) == ["/orgs/testorg/installation"]


def test_explicit_installation_id_skips_discovery(github_repo, fake_github):
    assert set(github_repo.list(profile="github_inst")) == {"repo-a", "repo-b"}
    assert not _discovery_requests(fake_github)


def test_user_owner_falls_back_to_user_installation(github_repo, fake_github):
    # Private repos are not included: installation tokens have no
    # associated user to compare the owner against
    assert set(github_repo.list(profile="github_user")) == {"repo-a"}
    assert _discovery_requests(fake_github) == [
        "/orgs/user1/installation",
        "/users/user1/installation",
    ]
    # The token was minted for the user installation
    (token_meta,) = (
        meta for tok, meta in fake_github.app_tokens.items() if tok != fake_github.app_token
    )
    assert token_meta["account"] == "user1"


def test_scoped_permissions_are_requested(github_repo, fake_github):
    assert set(github_repo.list(profile="github_scoped")) == {"repo-a", "repo-b"}
    mints = fake_github.filter_requests(path="/app/installations/*/access_tokens")
    assert len(mints) == 1
    assert mints[0].body == {"permissions": {"contents": "read", "metadata": "read"}}
    # The minted token itself carries the restrictions
    (token_meta,) = (
        meta for tok, meta in fake_github.app_tokens.items() if tok != fake_github.app_token
    )
    assert token_meta["permissions"] == {"contents": "read", "metadata": "read"}


def test_scoped_profiles_do_not_share_connections(github_repo, fake_github):
    """
    The same app+owner with different permission restrictions derives
    distinct connection identities - each profile mints its own,
    appropriately restricted token.
    """
    github_repo.list()
    github_repo.list(profile="github_scoped")
    mints = fake_github.filter_requests(path="/app/installations/*/access_tokens")
    assert [req.body["permissions"] for req in mints] == [
        {},
        {"contents": "read", "metadata": "read"},
    ]


def test_missing_owner_fails_with_intended_error(github_repo):
    with pytest.raises(CommandExecutionError, match="requires the 'owner' parameter"):
        github_repo.list(profile="github_noowner")


def test_not_installed_fails_with_intended_error(github_repo):
    with pytest.raises(CommandExecutionError, match="does not appear to be installed"):
        github_repo.list(profile="github_badowner")


def _mints(fake_github):
    return fake_github.filter_requests(path="/app/installations/*/access_tokens")


def _minted_tokens(fake_github):
    """
    The currently valid app tokens minted during the test, excluding
    the static one (used by the installation token tests).
    """
    return {tok for tok in fake_github.app_tokens if tok != fake_github.app_token}


def test_revoke_app_token(modules, github_repo, fake_github):
    github_repo.list()
    (initial_token,) = _minted_tokens(fake_github)
    assert modules.github.revoke_app_token() is True
    assert len(fake_github.filter_requests(method="DELETE", path="/installation/token")) == 1
    # The token was really invalidated - requests with it would 401
    assert not _minted_tokens(fake_github)
    # The cached connection was evicted, hence the next call succeeds
    # by minting a fresh token
    github_repo.list()
    assert _minted_tokens(fake_github)
    assert initial_token not in _minted_tokens(fake_github)


def test_revoked_connection_requires_eviction(minion_opts):
    """
    PyGithub only mints a new token once the current one nears expiry,
    not in response to auth failures: a connection surviving revocation
    keeps presenting the revoked token. This pins the behavior
    ``github.revoke_app_token``'s context eviction accounts for - if
    this test starts failing, the eviction may have become obsolete.
    """
    conn = gh_profile.get_conn("github", opts=minion_opts, context={})
    assert conn.query(["orgs", "testorg"])["login"] == "testorg"
    revoke_installation_token(conn)
    with pytest.raises(GitHubApiError, match="401"):
        conn.query(["orgs", "testorg"])


def test_revoke_app_token_evicts_shared_profiles(modules, github_repo, fake_github):
    """
    ``github`` and ``github_inst`` share one connection (same app,
    owner and API URL). Revoking via one profile must evict the other
    as well - it holds the same, now invalid, token.
    """
    github_repo.list()
    github_repo.list(profile="github_inst")
    assert len(_mints(fake_github)) == 1
    modules.github.revoke_app_token()
    github_repo.list(profile="github_inst")
    assert len(_mints(fake_github)) == 2


def test_revoke_app_token_requires_app_profile(modules):
    with pytest.raises(CommandExecutionError, match="Only GitHub App"):
        modules.github.revoke_app_token(profile="github_pat")


@pytest.fixture
def short_lived_tokens(fake_github):
    """
    Mint tokens that are already within PyGithub's refresh threshold
    (20s), making it refresh the token before each request.
    """
    default_validity = fake_github.app_token_validity
    fake_github.app_token_validity = timedelta(seconds=15)
    try:
        yield
    finally:
        fake_github.app_token_validity = default_validity


@pytest.mark.usefixtures("short_lived_tokens")
def test_tokens_are_refreshed_before_expiry(modules, github_repo, fake_github):
    """
    Tokens nearing expiry are replaced transparently (and the fake
    rejects expired ones), so calls keep succeeding without any
    token handling by the caller.
    """
    assert set(github_repo.list()) == {"repo-a", "repo-b"}
    mints = len(_mints(fake_github))
    assert mints >= 1
    # Served from the API (never conn-cached), requiring a live token
    assert modules.github.rate_limit()["core"]["limit"] == 5000
    assert len(_mints(fake_github)) > mints


@pytest.fixture
def cached_app_opts(minion_opts, fake_github):  # pylint: disable=unused-argument
    """
    Opts with an app profile that keeps the default-enabled persistent
    cache, flushed after the test (it outlives the fake state reset by
    design).
    """
    opts = copy.deepcopy(minion_opts)
    opts["github_cached"] = {key: val for key, val in opts["github"].items() if key != "cache"}
    try:
        yield opts
    finally:
        shutil.rmtree(os.path.join(minion_opts["cachedir"], CACHE_ROOT), ignore_errors=True)


def test_installation_discovery_persists_across_processes(cached_app_opts, fake_github):
    """
    Fresh contexts simulate separate processes (as with
    ``salt-call --local``): the connection identity derives from the
    app's identity instead of its short-lived installation tokens, so
    the discovered installation is served from the persistent cache.
    """
    conn = gh_profile.get_conn("github_cached", opts=cached_app_opts, context={})
    assert conn.ident == get_app_connection_ident(fake_github.app_id, "testorg", fake_github.url)
    assert len(_discovery_requests(fake_github)) == 1
    conn2 = gh_profile.get_conn("github_cached", opts=cached_app_opts, context={})
    assert conn2.ident == conn.ident
    assert len(_discovery_requests(fake_github)) == 1
