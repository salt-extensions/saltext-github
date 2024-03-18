from unittest import mock

import pytest
import salt.modules.config as config_module
import saltext.github.modules.github as github_module
from salt.exceptions import CommandExecutionError


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


def test__check_ruleset_params():
    ## test no valid config
    with pytest.raises(CommandExecutionError):
        github_module._check_ruleset_params(profile="test_ruleset")

    # test cli config
    kwargs = {"ruleset_type": "repo", "repo_name": "mock_repo_name", "owner": "mock_owner"}
    ret = github_module._check_ruleset_params(profile="test_ruleset", **kwargs)
    assert ret == (
        {
            "ruleset_type": "repo",
            "repo_name": "mock_repo_name",
            "owner": "mock_owner",
            "header_dict": {},
        },
        "repos/mock_owner/mock_repo_name/rulesets",
    )


def test_get_ruleset(params):
    params["ruleset_id"] = 1

    # test mock 200 status
    mock_query = {"dict": {"id": "1"}, "status": 200}
    expected = {"id": "1"}

    with mock.patch("salt.utils.http.query", return_value=mock_query):
        assert github_module.get_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    mock_query = {"error": "404 not found", "status": 404}
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with mock.patch("salt.utils.http.query", return_value=mock_query):
        assert github_module.get_ruleset(profile="test_ruleset", **params) == expected

    # test mock empty return
    expected = {"comment": "Error getting ruleset", "result": False}
    with mock.patch("salt.utils.http.query", return_value={}):
        assert github_module.get_ruleset(profile="test_ruleset", **params) == expected


def test_add_ruleset(params):
    params["ruleset_params"] = {"name": "mock_name", "enforcement": "disabled"}

    # test mock 201 status
    mock_query = {"dict": {"name": "mock_name", "enforcement": "disabled"}, "status": 201}

    expected = {"name": "mock_name", "enforcement": "disabled"}

    with mock.patch("salt.utils.http.query", return_value=mock_query):
        assert github_module.add_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with mock.patch(
        "salt.utils.http.query", return_value={"error": "404 not found", "status": 404}
    ):
        assert github_module.add_ruleset(profile="test_ruleset", **params) == expected

    # test mock empty return
    expected = {"comment": "Error adding ruleset", "result": False}

    with mock.patch("salt.utils.http.query", return_value={}):
        assert github_module.add_ruleset(profile="test_ruleset", **params) == expected


def test_list_rulesets(params):

    # test mock 200 status
    mock_query = {
        "dict": [{"name": "mock_ruleset_1"}, {"name": "mock_ruleset_2"}],
        "status": 200,
    }

    expected = [{"name": "mock_ruleset_1"}, {"name": "mock_ruleset_2"}]

    with mock.patch("salt.utils.http.query", return_value=mock_query):
        assert github_module.list_rulesets(profile="test_ruleset", **params) == expected

    # test mock 200 status, no rulesets returned
    mock_query = {"dict": [], "status": 200}
    expected = None

    with mock.patch("salt.utils.http.query", return_value=mock_query):
        assert github_module.list_rulesets(profile="test_ruleset", **params) == expected

    # test mock 404 error
    mock_query = {"error": "404 not found", "status": 404}
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with mock.patch("salt.utils.http.query", return_value=mock_query):
        assert github_module.list_rulesets(profile="test_ruleset", **params) == expected

    # test mock empty return
    expected = {"comment": "Error getting rulesets", "result": False}
    with mock.patch("salt.utils.http.query", return_value={}):
        assert github_module.list_rulesets(profile="test_ruleset", **params) == expected


def test_update_ruleset(params):
    params["ruleset_params"] = {"name": "mock_name", "enforcement": "disabled"}
    params["ruleset_id"] = 1

    # test mock 200 status
    mock_query = {"dict": {"name": "mock_name", "enforcement": "disabled"}, "status": 200}

    expected = {"name": "mock_name", "enforcement": "disabled"}

    with mock.patch("salt.utils.http.query", return_value=mock_query):
        assert github_module.update_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    mock_query = {"error": "404 not found", "status": 404}
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with mock.patch("salt.utils.http.query", return_value=mock_query):
        assert github_module.update_ruleset(profile="test_ruleset", **params) == expected

    # test mock empty return
    expected = {"comment": "Error updating ruleset", "result": False}
    with mock.patch("salt.utils.http.query", return_value={}):
        assert github_module.update_ruleset(profile="test_ruleset", **params) == expected


def test_delete_ruleset(params):
    params["ruleset_id"] = 1

    # test mock 204 status
    mock_query = {"status": 204}
    expected = {"comment": "ruleset 1 successfully deleted", "status": 204}

    with mock.patch("salt.utils.http.query", return_value=mock_query):
        assert github_module.delete_ruleset(profile="test_ruleset", **params) == expected

    # test mock 404 error
    mock_query = {"error": "404 not found", "status": 404}
    expected = {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }

    with mock.patch("salt.utils.http.query", return_value=mock_query):
        assert github_module.delete_ruleset(profile="test_ruleset", **params) == expected

    # test mock empty return
    expected = {"comment": "Error deleting ruleset", "result": False}
    with mock.patch("salt.utils.http.query", return_value={}):
        assert github_module.delete_ruleset(profile="test_ruleset", **params) == expected
