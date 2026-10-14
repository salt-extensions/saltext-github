from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.modules import github as github_mod
from saltext.github.utils.gh.exceptions import GitHubApiError

RULESET_PARAMS = {"name": "mock_name", "enforcement": "disabled"}

# Function-specific call kwargs and the comment returned on unexpected errors
RULESET_FUNCS = {
    "get_ruleset": ({"ruleset_id": 1}, "Error getting ruleset"),
    "add_ruleset": ({"ruleset_params": RULESET_PARAMS}, "Error adding ruleset"),
    "list_rulesets": ({}, "Error getting rulesets"),
    "update_ruleset": (
        {"ruleset_id": 1, "ruleset_params": RULESET_PARAMS},
        "Error updating ruleset",
    ),
    "delete_ruleset": ({"ruleset_id": 1}, "Error deleting ruleset"),
}


@pytest.fixture
def configure_loader_modules():
    return {
        github_mod: {
            "__opts__": {
                "github": {"token": "token_from_default_profile"},
                "test_ruleset": {"ruleset_type": "mocked_value"},
                "sdb_profile": {"token": "sdb://osenv/GITHUB_TOKEN"},
            },
        },
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


@pytest.fixture
def conn():
    conn_mock = MagicMock()
    with patch.object(github_mod, "_get_conn", autospec=True, return_value=conn_mock):
        yield conn_mock


def _call_ruleset_func(func, params):
    return getattr(github_mod, func)(profile="test_ruleset", **params, **RULESET_FUNCS[func][0])


@pytest.mark.usefixtures("conn")
def test_add_team_repo_reports_permission_failure():
    with (
        patch.object(github_mod.gh_teams, "get", autospec=True, return_value={"slug": "team"}),
        patch.object(
            github_mod.gh_teams,
            "add_repo",
            autospec=True,
            side_effect=GitHubApiError("Failed setting permission push"),
        ),
        patch.object(github_mod, "log", autospec=True) as log_mock,
    ):
        assert github_mod.add_team_repo("repo", "team", permission="push") is False
    assert "Failed setting permission" in log_mock.error.call_args[0][0]


def test_get_issue_without_id_returns_empty(conn):
    conn.repo_query.return_value = {"message": "no id here"}
    assert not github_mod.get_issue(1, repo_name="repo")


def test_get_milestone_without_id_returns_empty(conn):
    conn.repo_query.return_value = {"message": "no id here"}
    assert not github_mod.get_milestone(1, repo_name="repo")


def test__get_config_value_renders_sdb_uris():
    # This matters for pillar-sourced profiles, which are not rendered
    # by Salt automatically, unlike values in the minion configuration.
    def fake_sdb_get(value, *args, **kwargs):  # pylint: disable=unused-argument
        if isinstance(value, str) and value.startswith("sdb://"):
            return "rendered-token"
        return value

    with patch("salt.utils.sdb.sdb_get", side_effect=fake_sdb_get):
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


@pytest.mark.parametrize(
    "func,query_ret,expected",
    (
        ("get_ruleset", {"id": "1"}, {"id": "1"}),
        ("add_ruleset", RULESET_PARAMS, RULESET_PARAMS),
        (
            "list_rulesets",
            [{"name": "mock_ruleset_1"}, {"name": "mock_ruleset_2"}],
            {"rulesets": [{"name": "mock_ruleset_1"}, {"name": "mock_ruleset_2"}]},
        ),
        ("list_rulesets", [], {"rulesets": None}),
        ("update_ruleset", RULESET_PARAMS, RULESET_PARAMS),
        ("delete_ruleset", None, {"comment": "ruleset 1 successfully deleted"}),
    ),
)
def test_ruleset_funcs_success(func, query_ret, expected, params, conn):
    conn.query.return_value = query_ret
    assert _call_ruleset_func(func, params) == expected


@pytest.mark.parametrize("func", RULESET_FUNCS)
def test_ruleset_funcs_api_error(func, params, conn):
    conn.query.side_effect = GitHubApiError("404 not found", status=404)
    assert _call_ruleset_func(func, params) == {
        "comment": "GitHub Response Status Code: 404 not found",
        "error": "404 not found",
        "status": 404,
        "result": False,
    }


@pytest.mark.parametrize("func", RULESET_FUNCS)
def test_ruleset_funcs_unexpected_error(func, params, conn):
    conn.query.side_effect = CommandExecutionError
    assert _call_ruleset_func(func, params) == {
        "comment": RULESET_FUNCS[func][1],
        "result": False,
    }


def test_add_ruleset_requires_name_and_enforcement(params):
    params["ruleset_params"] = {"name": "mock_name"}

    with pytest.raises(CommandExecutionError, match="enforcement"):
        github_mod.add_ruleset(profile="test_ruleset", **params)


def test_ruleset_error_ret_includes_response_data():
    err = GitHubApiError("422 invalid", status=422, data={"message": "invalid"})
    assert github_mod._ruleset_error_ret(err) == {
        "status": 422,
        "error": "422 invalid",
        "dict": {"message": "invalid"},
        "comment": "GitHub Response Status Code: 422 invalid",
        "result": False,
    }
