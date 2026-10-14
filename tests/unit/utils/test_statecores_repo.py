from contextlib import ExitStack
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh.exceptions import GitHubApiError
from saltext.github.utils.gh.exceptions import GitHubNotFoundError
from saltext.github.utils.gh.statecores import repo as sc_repo


@pytest.fixture
def gh_mocks():
    mocks = {}
    with ExitStack() as stack:
        for mod, funcs in (
            (sc_repo.gh_repos, ("list_all", "get_info", "create", "update", "get_teams")),
            (sc_repo.gh_teams, ("find", "list_repos", "add_repo", "remove_repo")),
        ):
            for func in funcs:
                mocks[func] = stack.enter_context(patch.object(mod, func, autospec=True))
        mocks["find"].return_value = {"slug": "team-a"}
        mocks["add_repo"].side_effect = GitHubApiError(FAILURE_MSG)
        yield mocks


@pytest.fixture
def conn():
    return MagicMock()


FAILURE_MSG = "Failed setting permission push on repo repo for team Team A."


def test_present_reports_team_association_failure_on_create(gh_mocks, conn):
    gh_mocks["get_info"].side_effect = GitHubNotFoundError("missing")
    with pytest.raises(CommandExecutionError, match=FAILURE_MSG):
        sc_repo.present(conn, "repo", teams={"Team A": "push"})


def test_present_reports_team_association_failure_on_added_team(gh_mocks, conn):
    gh_mocks["get_info"].return_value = {}
    gh_mocks["get_teams"].return_value = []
    with pytest.raises(CommandExecutionError, match=FAILURE_MSG):
        sc_repo.present(conn, "repo", teams={"Team A": "push"})


def test_present_reports_permission_update_failure(gh_mocks, conn):
    gh_mocks["get_info"].return_value = {}
    gh_mocks["get_teams"].return_value = [{"name": "Team A"}]
    gh_mocks["list_repos"].return_value = {"repo": {"permission": "pull"}}
    with pytest.raises(CommandExecutionError, match=FAILURE_MSG):
        sc_repo.present(conn, "repo", teams={"Team A": "push"})


def test_present_reports_partial_team_changes(gh_mocks, conn):
    gh_mocks["get_info"].return_value = {}
    gh_mocks["get_teams"].return_value = []
    gh_mocks["add_repo"].side_effect = [None, GitHubApiError(FAILURE_MSG)]
    with pytest.raises(CommandExecutionError, match=FAILURE_MSG) as exc:
        sc_repo.present(conn, "repo", teams={"Team A": "push", "Team B": "push"})
    assert exc.value.changes == {"teams_added": ["Team A"]}


def test_present_reports_partial_changes_on_create(gh_mocks, conn):
    gh_mocks["get_info"].side_effect = GitHubNotFoundError("missing")
    gh_mocks["add_repo"].side_effect = [None, GitHubApiError(FAILURE_MSG)]
    with pytest.raises(CommandExecutionError, match=FAILURE_MSG) as exc:
        sc_repo.present(conn, "repo", teams={"Team A": "push", "Team B": "push"})
    assert exc.value.changes == {"created": "repo", "teams_added": ["Team A"]}
