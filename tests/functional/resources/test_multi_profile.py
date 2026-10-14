"""
Tests for per-owner profile overrides in the ``github`` resource
declaration (``owners`` as a mapping).
"""

import copy

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import profile as gh_profile


@pytest.fixture(scope="module")
def resource_decl():
    return {
        "profile": "github",
        "owners": {
            "testorg": {},
            "otherorg": {"profile": "github_other"},
        },
    }


@pytest.fixture(scope="module")
def res_opts(minion_opts, resource_decl, github_profile):
    opts = copy.deepcopy(minion_opts)
    opts["pillar"] = {"resources": {"github": resource_decl}}
    # Second profile: same token/API URL (the fake serves one token),
    # scoped to the other organization.
    opts["github_other"] = {
        "token": github_profile["token"],
        "owner": "otherorg",
    }
    if api_url := github_profile.get("api_url"):
        opts["github_other"]["api_url"] = api_url
    return opts


@pytest.fixture
def connection(resource_funcs, res_opts):
    resource_funcs["github.init"](res_opts)
    return resource_funcs


def test_owner_profile_resolution(res_opts):
    assert gh_profile.resource_owner_profile(res_opts, "testorg") == "github"
    assert gh_profile.resource_owner_profile(res_opts, "otherorg") == "github_other"
    # Owner matching is case-insensitive
    assert gh_profile.resource_owner_profile(res_opts, "OtherOrg") == "github_other"
    # Undeclared owners fall back to the default profile
    assert gh_profile.resource_owner_profile(res_opts, "someone-else") == "github"
    assert gh_profile.resource_profiles(res_opts) == ["github", "github_other"]


def test_owners_mapping_and_list_forms(res_opts):
    assert gh_profile.resource_owners(res_opts) == ["testorg", "otherorg"]
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["owners"] = ["testorg"]
    assert gh_profile.resource_owners(opts) == ["testorg"]
    assert gh_profile.resource_owner_profile(opts, "testorg") == "github"
    assert gh_profile.resource_profiles(opts) == ["github"]


def test_init_validates_all_profiles(resource_funcs, res_opts):
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["owners"]["otherorg"]["profile"] = "missing_profile"
    with pytest.raises(CommandExecutionError, match="could not be found.*missing_profile"):
        resource_funcs["github.init"](opts)


def test_discover_union_across_profiles(connection, res_opts):
    assert connection["github.discover"](res_opts) == [
        "otherorg/other-repo",
        "testorg/repo-a",
        "testorg/repo-b",
    ]


def test_discover_uses_owner_profile(connection, res_opts):
    """
    A broken per-owner profile must break exactly that owner's listing,
    proving discovery resolves connections per owner.
    """
    opts = copy.deepcopy(res_opts)
    opts["github_bad"] = dict(opts["github_other"], token="wrong-token")
    opts["pillar"]["resources"]["github"]["owners"]["otherorg"]["profile"] = "github_bad"
    with pytest.raises(CommandExecutionError):
        connection["github.discover"](opts)
    # The default-profile owner still works on its own
    opts["pillar"]["resources"]["github"]["owners"].pop("otherorg")
    assert connection["github.discover"](opts) == ["testorg/repo-a", "testorg/repo-b"]


def test_grains_per_owner(connection, for_resource):
    with for_resource("otherorg/other-repo"):
        grains = connection["github.grains"]()
    assert grains["github"]["full_name"] == "otherorg/other-repo"
    assert grains["github"]["owner"] == "otherorg"


def test_exec_resolves_per_owner_profile(res_modules, for_resource, loader_context):
    with for_resource("otherorg/other-repo"):
        info = res_modules["repo.info"]()
    assert info["owner"] == "otherorg"
    # The connection was built from the github_other profile: its cache
    # key carries that profile's owner.
    conn_keys = [
        key for key in loader_context if isinstance(key, str) and key.startswith("github.")
    ]
    assert any(":otherorg:" in key for key in conn_keys)
