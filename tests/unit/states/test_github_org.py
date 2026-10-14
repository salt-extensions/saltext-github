from unittest import mock

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.states import github_org as github_org_mod
from saltext.github.utils.gh.exceptions import GitHubNotFoundError


@pytest.fixture
def configure_loader_modules():
    return {
        github_org_mod: {
            "__salt__": {
                "github_org.get_team": mock.MagicMock(side_effect=GitHubNotFoundError("missing")),
                "github_org.add_team": mock.MagicMock(),
                "github_org.add_team_member": mock.MagicMock(
                    side_effect=[None, CommandExecutionError("API hiccup")]
                ),
            },
            "__opts__": {"test": False},
        },
    }


def test_team_present_reports_partial_changes_on_failure():
    ret = github_org_mod.team_present("team", members=["user1", "user2"])
    assert ret["result"] is False
    assert ret["comment"] == "API hiccup"
    assert ret["changes"] == {"created": "team", "members_added": ["user1"]}
