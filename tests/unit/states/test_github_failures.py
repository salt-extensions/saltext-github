"""
Failure branches that require API-level failure injection which the
functional fake cannot produce (mutations that are accepted over HTTP
but reported as failed by the module layer).
"""

from unittest import mock

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.states import github as github_mod

_TEAM_TARGET = {"description": "desc", "permission": "pull", "privacy": "closed"}

FAILURE_CASES = (
    pytest.param(
        "present",
        "user1",
        {},
        {
            "get_user": {"return_value": {"in_org": False, "membership_state": "nonexistent"}},
            "add_user": {"return_value": False},
        },
        "Failed to add user",
        id="present-add",
    ),
    pytest.param(
        "absent",
        "user1",
        {},
        {
            "get_user": {"return_value": True},
            "remove_user": {"return_value": False},
        },
        "Failed to delete",
        id="absent-remove",
    ),
    pytest.param(
        "team_absent",
        "team",
        {},
        {
            "get_team": {"return_value": {"id": 1}},
            "remove_team": {"return_value": False},
        },
        "Failed to delete",
        id="team_absent-remove",
    ),
    pytest.param(
        "repo_absent",
        "repo",
        {},
        {
            "get_repo_info": {"return_value": {"name": "repo"}},
            "remove_repo": {"return_value": False},
        },
        "delete_repo scope",
        id="repo_absent-remove",
    ),
    pytest.param(
        "team_present",
        "team",
        {"description": "changed", "privacy": "closed", "permission": "pull"},
        {
            "get_team": {"return_value": _TEAM_TARGET},
            "edit_team": {"return_value": False},
        },
        "Failed to update team properties.",
        id="team_present-edit",
    ),
    pytest.param(
        "team_present",
        "team",
        {
            "description": "desc",
            "privacy": "closed",
            "permission": "pull",
            "repo_names": ["repo-b"],
        },
        {
            "get_team": {"return_value": _TEAM_TARGET},
            "list_team_repos": {"return_value": {"repo-a": {"permission": "pull"}}},
            "add_team_repo": {"return_value": True},
            "remove_team_repo": {"return_value": False},
        },
        "Failed to remove repo repo-a",
        id="team_present-remove-repo",
    ),
    pytest.param(
        "team_present",
        "team",
        {"description": "desc", "privacy": "closed", "permission": "pull", "members": {}},
        {
            "get_team": {"return_value": _TEAM_TARGET},
            "list_team_repos": {"return_value": {}},
            "list_members_without_mfa": {"return_value": []},
            "list_team_members": {"return_value": ["olduser"]},
            "remove_team_member": {"return_value": False},
        },
        "Failed to remove user olduser",
        id="team_present-remove-member",
    ),
    pytest.param(
        "repo_present",
        "repo",
        {"description": "new"},
        {
            "list_repos": {"return_value": ["repo"]},
            "get_repo_info": {"return_value": {"name": "repo", "description": "old"}},
            "edit_repo": {"return_value": False},
        },
        "Failed to update repo properties.",
        id="repo_present-edit",
    ),
    pytest.param(
        "repo_present",
        "repo",
        {},
        {
            "list_repos": {"return_value": []},
            "get_repo_info": {"side_effect": CommandExecutionError("missing")},
            "add_repo": {"return_value": False},
        },
        "Failed to create repo",
        id="repo_present-create",
    ),
    pytest.param(
        "repo_present",
        "repo",
        {},
        {
            "list_repos": {"return_value": []},
            "get_repo_info": {"side_effect": CommandExecutionError("missing")},
            "add_repo": {"return_value": True},
            # The post-creation team fetch keeps returning 404
            "get_repo_teams": {"side_effect": CommandExecutionError("404")},
        },
        "Failed to verify repo",
        id="repo_present-verify-after-create",
    ),
    pytest.param(
        "repo_present",
        "repo",
        {"teams": {}},
        {
            "list_repos": {"return_value": ["repo"]},
            "get_repo_info": {"return_value": {"name": "repo"}},
            "get_repo_teams": {"return_value": [{"name": "Team A"}]},
            "remove_team_repo": {"return_value": False},
        },
        "Failed to remove repo repo from team Team A",
        id="repo_present-remove-team",
    ),
    pytest.param(
        "repo_present",
        "repo",
        {"teams": {"Team A": "push"}},
        {
            "list_repos": {"return_value": ["repo"]},
            "get_repo_info": {"return_value": {"name": "repo"}},
            "get_repo_teams": {"return_value": [{"name": "Team A"}]},
            "list_team_repos": {"return_value": {}},
        },
        "Failed to determine current permission",
        id="repo_present-permission-lookup",
    ),
    pytest.param(
        "repo_present",
        "repo",
        {"teams": {"Team A": "push"}},
        {
            "list_repos": {"return_value": ["repo"]},
            "get_repo_info": {"return_value": {"name": "repo"}},
            "get_repo_teams": {"return_value": [{"name": "Team A"}]},
            "list_team_repos": {"return_value": {"repo": {"permission": "pull"}}},
            "add_team_repo": {"return_value": False},
        },
        "Failed to set permission",
        id="repo_present-permission-change",
    ),
    pytest.param(
        "ruleset_absent",
        "rules",
        {"ruleset_type": "org"},
        {
            "list_rulesets": {"return_value": {"rulesets": [{"name": "rules", "id": 1}]}},
            "delete_ruleset": {"return_value": {"result": False, "comment": "403 nope"}},
        },
        "Failed to delete ruleset rules",
        id="ruleset_absent-delete",
    ),
    pytest.param(
        "ruleset_present",
        "rules",
        {"ruleset_type": "org", "ruleset_params": {"enforcement": "active"}},
        {
            "list_rulesets": {"return_value": {"rulesets": [{"name": "rules", "id": 1}]}},
            "get_ruleset": {"return_value": {"result": False, "comment": "403 nope"}},
        },
        "Could not get ruleset",
        id="ruleset_present-get",
    ),
)


@pytest.fixture
def configure_loader_modules():
    return {
        github_mod: {
            "__salt__": {},
            "__opts__": {"test": False},
        },
    }


@pytest.mark.parametrize("func,name,kwargs,salt_mocks,expected_comment", FAILURE_CASES)
def test_failure_is_reported(func, name, kwargs, salt_mocks, expected_comment):
    patched = {
        f"github.{salt_func}": mock.MagicMock(**spec) for salt_func, spec in salt_mocks.items()
    }
    with mock.patch.dict(github_mod.__salt__, patched), mock.patch("time.sleep"):
        ret = getattr(github_mod, func)(name, **kwargs)
    assert ret["result"] is False
    assert expected_comment in ret["comment"]
