from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import salt.modules.config as config_module
from salt.exceptions import CommandExecutionError

import saltext.github.modules.github as github_module


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {"config.option": config_module.option},
        "__opts__": {"test_ruleset": {"ruleset_type": "mocked_value"}},
    }
    return {
        github_module: module_globals,
        config_module: module_globals,
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


def test__query_decodes_json_string_data():
    requester = MagicMock()
    requester.requestJson.return_value = (200, {}, '{"written": true}')
    client = MagicMock(requester=requester)

    with patch.object(github_module, "_get_client", return_value=client):
        ret = github_module._query(
            "test_ruleset", action="repos", method="POST", data='{"some": "payload"}'
        )

    assert ret == {"status": 200, "headers": {}, "dict": {"written": True}}
    requester.requestJson.assert_called_once_with(
        "POST", "/repos", parameters=None, headers=None, input={"some": "payload"}
    )


def test__query_github_exception():
    import github as pygithub  # pylint: disable=import-outside-toplevel

    requester = MagicMock()
    requester.requestJson.side_effect = pygithub.GithubException(502, {"message": "bad gateway"})
    client = MagicMock(requester=requester)

    with patch.object(github_module, "_get_client", return_value=client):
        ret = github_module._query("test_ruleset", action="repos")

    assert ret["status"] == 502
    assert "bad gateway" in ret["error"]


def test__query_unexpected_exception():
    requester = MagicMock()
    requester.requestJson.side_effect = OSError("connection refused")
    client = MagicMock(requester=requester)

    with patch.object(github_module, "_get_client", return_value=client):
        with pytest.raises(CommandExecutionError, match="connection refused"):
            github_module._query("test_ruleset", action="repos")


def test__check_ruleset_params():
    ## test no valid config
    with pytest.raises(CommandExecutionError):
        github_module._check_ruleset_params(profile="test_ruleset")

    # test cli config
    kwargs = {"ruleset_type": "repo", "repo_name": "mock_repo_name", "owner": "mock_owner"}
    ret = github_module._check_ruleset_params(profile="test_ruleset", **kwargs)
    assert ret == (
        ["repos", "mock_owner", "mock_repo_name", "rulesets"],
        {},
        {
            "ruleset_type": "repo",
            "repo_name": "mock_repo_name",
            "owner": "mock_owner",
        },
    )


def test_get_ruleset(params):
    params["ruleset_id"] = 1

    # test mock 200 status
    mock_query = {"dict": {"id": "1"}, "status": 200}
    expected = {"id": "1"}

    with patch.object(github_module, "_query", return_value=mock_query):
        assert github_module.get_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    mock_query = {"error": "404 not found", "status": 404}
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with patch.object(github_module, "_query", return_value=mock_query):
        assert github_module.get_ruleset(profile="test_ruleset", **params) == expected

    # test mock empty return
    expected = {"comment": "Error getting ruleset", "result": False}
    with patch.object(github_module, "_query", side_effect=CommandExecutionError):
        assert github_module.get_ruleset(profile="test_ruleset", **params) == expected


def test_add_ruleset(params):
    params["ruleset_params"] = {"name": "mock_name", "enforcement": "disabled"}

    # test mock 201 status
    mock_query = {"dict": {"name": "mock_name", "enforcement": "disabled"}, "status": 201}

    expected = {"name": "mock_name", "enforcement": "disabled"}

    with patch.object(github_module, "_query", return_value=mock_query):
        assert github_module.add_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with patch.object(
        github_module, "_query", return_value={"error": "404 not found", "status": 404}
    ):
        assert github_module.add_ruleset(profile="test_ruleset", **params) == expected

    # test mock empty return
    expected = {"comment": "Error adding ruleset", "result": False}

    with patch.object(github_module, "_query", side_effect=CommandExecutionError):
        assert github_module.add_ruleset(profile="test_ruleset", **params) == expected


def test_list_rulesets(params):

    # test mock 200 status
    mock_query = {
        "dict": [{"name": "mock_ruleset_1"}, {"name": "mock_ruleset_2"}],
        "status": 200,
    }

    expected = {"rulesets": [{"name": "mock_ruleset_1"}, {"name": "mock_ruleset_2"}]}

    with patch.object(github_module, "_query", return_value=mock_query):
        assert github_module.list_rulesets(profile="test_ruleset", **params) == expected

    # test mock 200 status, no rulesets returned
    mock_query = {"dict": [], "status": 200}
    expected = {"rulesets": None}

    with patch.object(github_module, "_query", return_value=mock_query):
        assert github_module.list_rulesets(profile="test_ruleset", **params) == expected

    # test mock 404 error
    mock_query = {"error": "404 not found", "status": 404}
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with patch.object(github_module, "_query", return_value=mock_query):
        assert github_module.list_rulesets(profile="test_ruleset", **params) == expected

    # test mock empty return
    expected = {"comment": "Error getting rulesets", "result": False}
    with patch.object(github_module, "_query", side_effect=CommandExecutionError):
        assert github_module.list_rulesets(profile="test_ruleset", **params) == expected


def test_update_ruleset(params):
    params["ruleset_params"] = {"name": "mock_name", "enforcement": "disabled"}
    params["ruleset_id"] = 1

    # test mock 200 status
    mock_query = {"dict": {"name": "mock_name", "enforcement": "disabled"}, "status": 200}

    expected = {"name": "mock_name", "enforcement": "disabled"}

    with patch.object(github_module, "_query", return_value=mock_query):
        assert github_module.update_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    mock_query = {"error": "404 not found", "status": 404}
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with patch.object(github_module, "_query", return_value=mock_query):
        assert github_module.update_ruleset(profile="test_ruleset", **params) == expected

    # test mock empty return
    expected = {"comment": "Error updating ruleset", "result": False}
    with patch.object(github_module, "_query", side_effect=CommandExecutionError):
        assert github_module.update_ruleset(profile="test_ruleset", **params) == expected


def test_delete_ruleset(params):
    params["ruleset_id"] = 1

    # test mock 204 status
    mock_query = {"status": 204}
    expected = {"comment": "ruleset 1 successfully deleted", "status": 204}

    with patch.object(github_module, "_query", return_value=mock_query):
        assert github_module.delete_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    mock_query = {"error": "404 not found", "status": 404}
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with patch.object(github_module, "_query", return_value=mock_query):
        assert github_module.delete_ruleset(profile="test_ruleset", **params) == expected

    # test mock empty return
    expected = {"comment": "Error deleting ruleset", "result": False}
    with patch.object(github_module, "_query", side_effect=CommandExecutionError):
        assert github_module.delete_ruleset(profile="test_ruleset", **params) == expected
