from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from salt.exceptions import CommandExecutionError
from salt.modules import config as config_mod

from saltext.github.modules import github as github_mod
from saltext.github.utils.github import client as gh_client
from saltext.github.utils.github.exceptions import GitHubApiError


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {"config.get": config_mod.get},
        "__opts__": {
            "test_ruleset": {"ruleset_type": "mocked_value"},
            "sdb_profile": {"token": "sdb://osenv/GITHUB_TOKEN"},
        },
    }
    return {
        github_mod: module_globals,
        config_mod: module_globals,
    }


@pytest.fixture
def params():
    return {
        "ruleset_type": "repo",
        "owner": "mock_owner",
        "repo_name": "mock_repo_name",
        "org_name": "mock_org_name",
        "header_dict": {"Authorization": "mock_token"},
    }


@pytest.fixture(autouse=True)
def conn():
    with patch.object(github_mod, "_get_conn", return_value=MagicMock()):
        yield


def test_get_issue_without_id_returns_empty():
    with patch.object(gh_client, "query", return_value={"message": "no id here"}):
        assert not github_mod.get_issue(1, repo_name="repo")


def test_get_milestone_without_id_returns_empty():
    with patch.object(gh_client, "query", return_value={"message": "no id here"}):
        assert not github_mod.get_milestone(1, repo_name="repo")


def test__get_config_value_renders_sdb_uris():
    # This matters for pillar-sourced profiles, which are not rendered
    # by Salt automatically, unlike values in the minion configuration.
    def fake_sdb_get(value, *args, **kwargs):  # pylint: disable=unused-argument
        if isinstance(value, str) and value.startswith("sdb://"):
            return "rendered-token"
        return value

    with patch.object(config_mod.sdb, "sdb_get", side_effect=fake_sdb_get):
        assert github_mod._get_config_value("sdb_profile", "token") == "rendered-token"


def test__resolve_ruleset_params():
    ## test no valid config
    with pytest.raises(CommandExecutionError):
        github_mod._resolve_ruleset_params(profile="test_ruleset")

    # test cli config
    kwargs = {"ruleset_type": "repo", "repo_name": "mock_repo_name", "owner": "mock_owner"}
    ret = github_mod._resolve_ruleset_params(profile="test_ruleset", **kwargs)
    assert ret == {
        "ruleset_type": "repo",
        "repo_name": "mock_repo_name",
        "owner": "mock_owner",
        "headers": {},
    }


def test_get_ruleset(params):
    params["ruleset_id"] = 1

    # test mock 200 status
    with patch.object(gh_client, "query", return_value={"id": "1"}):
        assert github_mod.get_ruleset(profile="test_ruleset", **params) == {"id": "1"}

    # test mock 404 error
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with patch.object(gh_client, "query", side_effect=GitHubApiError("404 not found", status=404)):
        assert github_mod.get_ruleset(profile="test_ruleset", **params) == expected

    # test unexpected error
    expected = {"comment": "Error getting ruleset", "result": False}
    with patch.object(gh_client, "query", side_effect=CommandExecutionError):
        assert github_mod.get_ruleset(profile="test_ruleset", **params) == expected


def test_add_ruleset(params):
    params["ruleset_params"] = {"name": "mock_name", "enforcement": "disabled"}

    # test mock 201 status
    expected = {"name": "mock_name", "enforcement": "disabled"}

    with patch.object(gh_client, "query", return_value=expected):
        assert github_mod.add_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with patch.object(gh_client, "query", side_effect=GitHubApiError("404 not found", status=404)):
        assert github_mod.add_ruleset(profile="test_ruleset", **params) == expected

    # test unexpected error
    expected = {"comment": "Error adding ruleset", "result": False}

    with patch.object(gh_client, "query", side_effect=CommandExecutionError):
        assert github_mod.add_ruleset(profile="test_ruleset", **params) == expected


def test_add_ruleset_requires_name_and_enforcement(params):
    params["ruleset_params"] = {"name": "mock_name"}

    with pytest.raises(CommandExecutionError, match="enforcement"):
        github_mod.add_ruleset(profile="test_ruleset", **params)


def test_list_rulesets(params):

    # test mock 200 status
    with patch.object(
        gh_client, "query", return_value=[{"name": "mock_ruleset_1"}, {"name": "mock_ruleset_2"}]
    ):
        assert github_mod.list_rulesets(profile="test_ruleset", **params) == {
            "rulesets": [{"name": "mock_ruleset_1"}, {"name": "mock_ruleset_2"}]
        }

    # test mock 200 status, no rulesets returned
    with patch.object(gh_client, "query", return_value=[]):
        assert github_mod.list_rulesets(profile="test_ruleset", **params) == {"rulesets": None}

    # test mock 404 error
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with patch.object(gh_client, "query", side_effect=GitHubApiError("404 not found", status=404)):
        assert github_mod.list_rulesets(profile="test_ruleset", **params) == expected

    # test unexpected error
    expected = {"comment": "Error getting rulesets", "result": False}
    with patch.object(gh_client, "query", side_effect=CommandExecutionError):
        assert github_mod.list_rulesets(profile="test_ruleset", **params) == expected


def test_update_ruleset(params):
    params["ruleset_params"] = {"name": "mock_name", "enforcement": "disabled"}
    params["ruleset_id"] = 1

    # test mock 200 status
    expected = {"name": "mock_name", "enforcement": "disabled"}

    with patch.object(gh_client, "query", return_value=expected):
        assert github_mod.update_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with patch.object(gh_client, "query", side_effect=GitHubApiError("404 not found", status=404)):
        assert github_mod.update_ruleset(profile="test_ruleset", **params) == expected

    # test unexpected error
    expected = {"comment": "Error updating ruleset", "result": False}
    with patch.object(gh_client, "query", side_effect=CommandExecutionError):
        assert github_mod.update_ruleset(profile="test_ruleset", **params) == expected


def test_delete_ruleset(params):
    params["ruleset_id"] = 1

    # test mock 204 status
    expected = {"comment": "ruleset 1 successfully deleted"}

    with patch.object(gh_client, "query", return_value=None):
        assert github_mod.delete_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with patch.object(gh_client, "query", side_effect=GitHubApiError("404 not found", status=404)):
        assert github_mod.delete_ruleset(profile="test_ruleset", **params) == expected

    # test unexpected error
    expected = {"comment": "Error deleting ruleset", "result": False}
    with patch.object(gh_client, "query", side_effect=CommandExecutionError):
        assert github_mod.delete_ruleset(profile="test_ruleset", **params) == expected


def test_ruleset_error_ret_includes_response_data():
    err = GitHubApiError("422 invalid", status=422, data={"message": "invalid"})
    assert github_mod._ruleset_error_ret(err) == {
        "status": 422,
        "error": "422 invalid",
        "dict": {"message": "invalid"},
        "comment": "GitHub Response Status Code: 422 invalid",
        "result": False,
    }
