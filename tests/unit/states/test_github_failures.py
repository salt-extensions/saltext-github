"""
Failure branches that require API-level failure injection which the
functional fake cannot produce (mutations that are accepted over HTTP
but reported as failed by the module layer).
"""

from unittest import mock

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.states import github as github_mod


@pytest.fixture
def configure_loader_modules():
    return {
        github_mod: {
            "__salt__": {},
            "__opts__": {"test": False},
        },
    }


def _patch_salt(**funcs):
    return mock.patch.dict(
        github_mod.__salt__,
        {f"github.{name}": mock.MagicMock(**spec) for name, spec in funcs.items()},
    )


def test_present_add_failure():
    with _patch_salt(
        get_user={"return_value": {"in_org": False, "membership_state": "nonexistent"}},
        add_user={"return_value": False},
    ):
        ret = github_mod.present("user1")
    assert ret["result"] is False
    assert "Failed to add user" in ret["comment"]


def test_absent_remove_failure():
    with _patch_salt(
        get_user={"return_value": True},
        remove_user={"return_value": False},
    ):
        ret = github_mod.absent("user1")
    assert ret["result"] is False
    assert "Failed to delete" in ret["comment"]


def test_team_absent_remove_failure():
    with _patch_salt(
        get_team={"return_value": {"id": 1}},
        remove_team={"return_value": False},
    ):
        ret = github_mod.team_absent("team")
    assert ret["result"] is False
    assert "Failed to delete" in ret["comment"]


def test_repo_absent_remove_failure():
    with _patch_salt(
        get_repo_info={"return_value": {"name": "repo"}},
        remove_repo={"return_value": False},
    ):
        ret = github_mod.repo_absent("repo")
    assert ret["result"] is False
    assert "delete_repo scope" in ret["comment"]


_TEAM_TARGET = {"description": "desc", "permission": "pull", "privacy": "closed"}


def test_team_present_edit_failure():
    with _patch_salt(
        get_team={"return_value": _TEAM_TARGET},
        edit_team={"return_value": False},
    ):
        ret = github_mod.team_present(
            "team", description="changed", privacy="closed", permission="pull"
        )
    assert ret["result"] is False
    assert ret["comment"] == "Failed to update team properties."


def test_team_present_remove_repo_failure():
    with _patch_salt(
        get_team={"return_value": _TEAM_TARGET},
        list_team_repos={"return_value": {"repo-a": {"permission": "pull"}}},
        add_team_repo={"return_value": True},
        remove_team_repo={"return_value": False},
    ):
        ret = github_mod.team_present(
            "team",
            description="desc",
            privacy="closed",
            permission="pull",
            repo_names=["repo-b"],
        )
    assert ret["result"] is False
    assert "Failed to remove repo repo-a" in ret["comment"]


def test_team_present_remove_member_failure():
    with _patch_salt(
        get_team={"return_value": _TEAM_TARGET},
        list_team_repos={"return_value": {}},
        list_members_without_mfa={"return_value": []},
        list_team_members={"return_value": ["olduser"]},
        remove_team_member={"return_value": False},
    ):
        ret = github_mod.team_present(
            "team", description="desc", privacy="closed", permission="pull", members={}
        )
    assert ret["result"] is False
    assert "Failed to remove user olduser" in ret["comment"]


def test_repo_present_edit_failure():
    with _patch_salt(
        list_repos={"return_value": ["repo"]},
        get_repo_info={"return_value": {"name": "repo", "description": "old"}},
        edit_repo={"return_value": False},
    ):
        ret = github_mod.repo_present("repo", description="new")
    assert ret["result"] is False
    assert ret["comment"] == "Failed to update repo properties."


def test_repo_present_create_failure():
    with _patch_salt(
        list_repos={"return_value": []},
        get_repo_info={"side_effect": CommandExecutionError("missing")},
        add_repo={"return_value": False},
    ):
        ret = github_mod.repo_present("repo")
    assert ret["result"] is False
    assert "Failed to create repo" in ret["comment"]


def test_repo_present_verification_after_create_failure():
    # The post-creation team fetch keeps returning 404
    with (
        _patch_salt(
            list_repos={"return_value": []},
            get_repo_info={"side_effect": CommandExecutionError("missing")},
            add_repo={"return_value": True},
            get_repo_teams={"side_effect": CommandExecutionError("404")},
        ),
        mock.patch("time.sleep"),
    ):
        ret = github_mod.repo_present("repo")
    assert ret["result"] is False
    assert "Failed to verify repo" in ret["comment"]


def test_repo_present_remove_team_failure():
    with _patch_salt(
        list_repos={"return_value": ["repo"]},
        get_repo_info={"return_value": {"name": "repo"}},
        get_repo_teams={"return_value": [{"name": "Team A"}]},
        remove_team_repo={"return_value": False},
    ):
        ret = github_mod.repo_present("repo", teams={})
    assert ret["result"] is False
    assert "Failed to remove repo repo from team Team A" in ret["comment"]


def test_repo_present_permission_lookup_failure():
    with _patch_salt(
        list_repos={"return_value": ["repo"]},
        get_repo_info={"return_value": {"name": "repo"}},
        get_repo_teams={"return_value": [{"name": "Team A"}]},
        list_team_repos={"return_value": {}},
    ):
        ret = github_mod.repo_present("repo", teams={"Team A": "push"})
    assert ret["result"] is False
    assert "Failed to determine current permission" in ret["comment"]


def test_repo_present_permission_change_failure():
    with _patch_salt(
        list_repos={"return_value": ["repo"]},
        get_repo_info={"return_value": {"name": "repo"}},
        get_repo_teams={"return_value": [{"name": "Team A"}]},
        list_team_repos={"return_value": {"repo": {"permission": "pull"}}},
        add_team_repo={"return_value": False},
    ):
        ret = github_mod.repo_present("repo", teams={"Team A": "push"})
    assert ret["result"] is False
    assert "Failed to set permission" in ret["comment"]


def test_ruleset_absent_delete_failure():
    with _patch_salt(
        list_rulesets={"return_value": {"rulesets": [{"name": "rules", "id": 1}]}},
        delete_ruleset={"return_value": {"result": False, "comment": "403 nope"}},
    ):
        ret = github_mod.ruleset_absent("rules", ruleset_type="org")
    assert ret["result"] is False
    assert "Failed to delete ruleset rules" in ret["comment"]


def test_ruleset_present_get_failure():
    with _patch_salt(
        list_rulesets={"return_value": {"rulesets": [{"name": "rules", "id": 1}]}},
        get_ruleset={"return_value": {"result": False, "comment": "403 nope"}},
    ):
        ret = github_mod.ruleset_present(
            "rules", ruleset_type="org", ruleset_params={"enforcement": "active"}
        )
    assert ret["result"] is False
    assert ret["comment"] == "Could not get ruleset"
