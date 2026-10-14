"""
Tests for the ``github`` resource type's connection module
(init/discover/grains/ping, pillar declaration handling, opts-based
profile resolution).
"""

import copy

import pytest
import salt.loader
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import profile as gh_profile


@pytest.fixture
def connection(resource_funcs, res_opts):
    resource_funcs["github.init"](res_opts)
    return resource_funcs


def test_virtual(resource_funcs):
    assert "github.discover" in resource_funcs


def test_init_and_initialized(resource_funcs, res_opts):
    assert resource_funcs["github.initialized"]() is False
    resource_funcs["github.init"](res_opts)
    assert resource_funcs["github.initialized"]() is True
    resource_funcs["github.shutdown"](res_opts)
    assert resource_funcs["github.initialized"]() is False


def test_init_missing_profile(resource_funcs, res_opts):
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"] = {"profile": "nonexistent"}
    with pytest.raises(CommandExecutionError, match="could not be found.*nonexistent"):
        resource_funcs["github.init"](opts)


def test_discover_default_owner(connection, res_opts):
    # The profile's owner is testorg (via the legacy org_name alias)
    assert connection["github.discover"](res_opts) == ["testorg/repo-a", "testorg/repo-b"]


def test_discover_multiple_owners(connection, res_opts):
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["owners"] = ["testorg", "user1"]
    # user1's private user-repo is visible since user1 is the token's user
    assert connection["github.discover"](opts) == [
        "testorg/repo-a",
        "testorg/repo-b",
        "user1/repo-a",
        "user1/user-repo",
    ]


def test_discover_include_patterns(connection, res_opts):
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["owners"] = ["testorg", "user1"]
    # Patterns with a slash match the full name, others the bare name
    opts["pillar"]["resources"]["github"]["repos"] = ["user1/*"]
    assert connection["github.discover"](opts) == ["user1/repo-a", "user1/user-repo"]
    opts["pillar"]["resources"]["github"]["repos"] = ["repo-a"]
    assert connection["github.discover"](opts) == ["testorg/repo-a", "user1/repo-a"]


def test_discover_exclude_patterns(connection, res_opts):
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["exclude"] = ["repo-b"]
    assert connection["github.discover"](opts) == ["testorg/repo-a"]


def test_discover_archived(connection, res_opts, fake_org):
    fake_org.get_repo("repo-b").update(archived=True)
    assert connection["github.discover"](res_opts) == ["testorg/repo-a"]
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["include_archived"] = True
    assert connection["github.discover"](opts) == ["testorg/repo-a", "testorg/repo-b"]


def test_discover_per_owner_patterns(connection, res_opts):
    """
    ``repos``/``exclude`` can be overridden per owner; owners without
    their own value inherit the declaration-level one.
    """
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["repos"] = ["repo-*"]
    opts["pillar"]["resources"]["github"]["owners"] = {
        "testorg": {},
        "user1": {"repos": ["user-*"]},
    }
    assert connection["github.discover"](opts) == [
        "testorg/repo-a",
        "testorg/repo-b",
        "user1/user-repo",
    ]
    opts["pillar"]["resources"]["github"]["owners"]["testorg"]["exclude"] = ["repo-b"]
    assert connection["github.discover"](opts) == ["testorg/repo-a", "user1/user-repo"]


def test_discover_per_owner_archived(connection, res_opts, fake_org, fake_user):
    fake_org.get_repo("repo-b").update(archived=True)
    fake_user.get_repo("user-repo").update(archived=True)
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["owners"] = {
        "testorg": {"include_archived": True},
        "user1": {},
    }
    assert connection["github.discover"](opts) == [
        "testorg/repo-a",
        "testorg/repo-b",
        "user1/repo-a",
    ]


def test_empty_decl_derived_user(resource_funcs, res_opts, github_profile, for_resource):
    """
    A bare ``resources: github: {}`` declaration with a minimal default
    profile (token only) manages the token user's repositories.
    """
    opts = copy.deepcopy(res_opts)
    opts["github"] = {
        "token": github_profile["token"],
    }
    if api_url := github_profile.get("api_url"):
        opts["github"]["api_url"] = api_url
    opts["pillar"]["resources"]["github"] = {}
    resource_funcs["github.init"](opts)
    assert resource_funcs["github.discover"](opts) == ["user1/repo-a", "user1/user-repo"]
    with for_resource("user1/user-repo"):
        grains = resource_funcs["github.grains"]()
    assert grains["github"]["owner"] == "user1"


def test_empty_decl_none_value(resource_funcs, res_opts):
    """
    ``resources: github:`` (an empty YAML value) behaves like an empty
    declaration.
    """
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"] = None
    resource_funcs["github.init"](opts)
    # The default profile's owner (testorg via the org_name alias) applies
    assert resource_funcs["github.discover"](opts) == ["testorg/repo-a", "testorg/repo-b"]


def test_empty_decl_profile_owner(resource_funcs, res_opts, github_profile):
    """
    A bare declaration with an owner-scoped default profile manages
    that owner's repositories.
    """
    opts = copy.deepcopy(res_opts)
    opts["github"] = {
        "token": github_profile["token"],
        "owner": "testorg",
    }
    if api_url := github_profile.get("api_url"):
        opts["github"]["api_url"] = api_url
    opts["pillar"]["resources"]["github"] = {}
    resource_funcs["github.init"](opts)
    assert resource_funcs["github.discover"](opts) == ["testorg/repo-a", "testorg/repo-b"]


def test_decl_alternative_profile_with_exclude(resource_funcs, res_opts, github_profile):
    """
    A declaration naming an alternative profile (token user derived)
    plus root-level exclude patterns — without the default ``github``
    profile even existing.
    """
    opts = copy.deepcopy(res_opts)
    opts.pop("github")
    opts.pop("github_noprivacy", None)
    opts["github_repos"] = {
        "token": github_profile["token"],
    }
    if api_url := github_profile.get("api_url"):
        opts["github_repos"]["api_url"] = api_url
    opts["pillar"]["resources"]["github"] = {
        "profile": "github_repos",
        "exclude": ["user-*"],
    }
    resource_funcs["github.init"](opts)
    assert resource_funcs["github.discover"](opts) == ["user1/repo-a"]


def test_owner_setting_inheritance(res_opts):
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"].update(
        {
            "repos": ["root-*"],
            "owners": {"testorg": {"repos": ["own-*"]}, "User1": {}},
        }
    )
    # Owner override wins, case-insensitively
    assert gh_profile.resource_owner_setting(opts, "TestOrg", "repos") == ["own-*"]
    # Unset per-owner keys inherit the declaration level, then the default
    assert gh_profile.resource_owner_setting(opts, "user1", "repos") == ["root-*"]
    assert gh_profile.resource_owner_setting(opts, "user1", "exclude", []) == []
    # Owners not declared at all inherit the declaration level as well
    assert gh_profile.resource_owner_setting(opts, "someone-else", "repos") == ["root-*"]


def test_grains(connection, for_resource):
    with for_resource("testorg/repo-a"):
        grains = connection["github.grains"]()
    assert grains == {
        "github": {
            "id": "testorg/repo-a",
            "owner": "testorg",
            "repo": "repo-a",
            "full_name": "testorg/repo-a",
            "private": False,
            "fork": False,
            "default_branch": "main",
            "language": "Python",
            "html_url": "https://github.example.com/testorg/repo-a",
            "description": "Test repo repo-a",
            "homepage": None,
        }
    }


def test_grains_cold_context(res_opts, utils_loader, for_resource):
    """
    State runs rebuild the connection module with a fresh context and
    re-call init() (salt.state.State.load_modules), so grains must work
    without any discover()-time warmup.
    """
    cold_context = {}
    funcs = salt.loader.resource(
        res_opts,
        utils=utils_loader,
        context=cold_context,
        loaded_base_name=f"{__name__}.cold",
    )
    funcs["github.init"](res_opts)
    with for_resource("user1/repo-a"):
        grains = funcs["github.grains"]()
    assert grains["github"]["description"] == "User-owned repo-a"
    assert grains["github"]["owner"] == "user1"


def test_grains_identity_routing(connection, for_resource):
    """
    The org repo and the user repo share the bare name; the owner half
    of the resource ID must disambiguate.
    """
    with for_resource("testorg/repo-a"):
        org_grains = connection["github.grains"]()
    with for_resource("user1/repo-a"):
        user_grains = connection["github.grains"]()
    assert org_grains["github"]["description"] == "Test repo repo-a"
    assert user_grains["github"]["description"] == "User-owned repo-a"


def test_grains_refresh(connection, for_resource, fake_org):
    with for_resource("testorg/repo-a"):
        assert connection["github.grains"]()["github"]["description"] == "Test repo repo-a"
        fake_org.get_repo("repo-a").update(description="Changed behind the cache")
        # Plain grains() serves from the warmed cache
        assert connection["github.grains"]()["github"]["description"] == "Test repo repo-a"
        refreshed = connection["github.grains_refresh"]()
    assert refreshed["github"]["description"] == "Changed behind the cache"


def test_ping(connection, for_resource):
    with for_resource("testorg/repo-a"):
        assert connection["github.ping"]() is True
    with for_resource("testorg/missing-repo"):
        assert connection["github.ping"]() is False


def test_profile_from_pillar(res_opts, github_profile):
    """
    Profiles are resolved from pillar as well as the minion config.
    """
    opts = copy.deepcopy(res_opts)
    opts.pop("github")
    with pytest.raises(CommandExecutionError, match="could not be found.*github"):
        gh_profile.get_config_value("github", "token", opts=opts)
    opts["pillar"]["github"] = dict(github_profile)
    assert gh_profile.get_config_value("github", "token", opts=opts) == github_profile["token"]


def test_profile_from_grains_and_master_config(res_opts, github_profile):
    """
    The remaining ``config.get`` sources work as well: grains and the
    master configuration (shared via ``pillar_opts`` as
    ``pillar["master"]``).
    """
    opts = copy.deepcopy(res_opts)
    opts.pop("github")
    opts["grains"]["github"] = dict(github_profile)
    assert gh_profile.get_config_value("github", "token", opts=opts) == github_profile["token"]
    opts = copy.deepcopy(res_opts)
    opts.pop("github")
    opts["pillar"]["master"] = {"github": dict(github_profile)}
    assert gh_profile.get_config_value("github", "token", opts=opts) == github_profile["token"]


def test_profile_lookup_order(res_opts, github_profile):
    """
    Like ``config.get``: minion config wins over grains, grains over
    pillar, pillar over master config — per value, so scopes missing an
    item fall through to later ones.
    """
    opts = copy.deepcopy(res_opts)
    opts.pop("github")
    opts["pillar"]["master"] = {"github": dict(github_profile, repo_name="from-master")}
    opts["pillar"]["github"] = {"repo_name": "from-pillar"}
    opts["grains"]["github"] = {"repo_name": "from-grains"}
    assert gh_profile.get_config_value("github", "repo_name", opts=opts) == "from-grains"
    opts["github"] = {"repo_name": "from-opts"}
    assert gh_profile.get_config_value("github", "repo_name", opts=opts) == "from-opts"
    # The grains/pillar profiles carry no token, the master one does
    assert gh_profile.get_config_value("github", "token", opts=opts) == github_profile["token"]


def test_profile_sdb_rendering(res_opts, github_profile, monkeypatch):
    """
    sdb:// URIs in profile values are rendered on access.
    """
    monkeypatch.setenv("FAKE_GITHUB_TOKEN", github_profile["token"])
    opts = copy.deepcopy(res_opts)
    opts["osenv"] = {"driver": "env"}
    opts["github"] = dict(github_profile, token="sdb://osenv/FAKE_GITHUB_TOKEN")
    assert gh_profile.get_config_value("github", "token", opts=opts) == github_profile["token"]
