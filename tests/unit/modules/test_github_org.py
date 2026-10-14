from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.modules import github_org as github_org_mod
from saltext.github.utils.gh.client import ModWrapper
from saltext.github.utils.gh.exceptions import GitHubApiError


@pytest.fixture
def configure_loader_modules():
    return {
        github_org_mod: {
            "__opts__": {"github": {"token": "token_from_default_profile"}},
        },
    }


@pytest.fixture
def conn():
    conn_mock = MagicMock()
    conn_mock.owner = "mock_org"
    conn_mock.bind.side_effect = lambda mod: ModWrapper(conn_mock, mod)
    with patch.object(github_org_mod, "_get_conn", autospec=True, return_value=conn_mock):
        yield conn_mock


@pytest.mark.usefixtures("conn")
def test_add_team_repo_reports_permission_failure():
    with (
        patch.object(github_org_mod.gh_teams, "find", autospec=True, return_value={"slug": "team"}),
        patch.object(
            github_org_mod.gh_teams,
            "add_repo",
            autospec=True,
            side_effect=GitHubApiError("Failed setting permission push"),
        ),
    ):
        with pytest.raises(CommandExecutionError, match="Failed setting permission push"):
            github_org_mod.add_team_repo("repo", "team", permission="push")
