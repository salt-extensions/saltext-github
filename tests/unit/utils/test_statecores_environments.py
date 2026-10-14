from contextlib import ExitStack
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh.statecores import environments as sc_environments


@pytest.fixture
def gh_mocks():
    mocks = {}
    with ExitStack() as stack:
        for func in (
            "get",
            "normalize",
            "branch_policy_from_patterns",
            "list_branch_policies",
            "set_",
            "create_branch_policy",
            "delete_branch_policy",
        ):
            mocks[func] = stack.enter_context(
                patch.object(sc_environments.gh_environments, func, autospec=True)
            )
        yield mocks


def test_present_reports_partial_branch_policy_changes(gh_mocks):
    policy = {"protected_branches": False, "custom_branch_policies": True}
    gh_mocks["get"].return_value = {"name": "release"}
    gh_mocks["normalize"].return_value = {"deployment_branch_policy": policy}
    gh_mocks["branch_policy_from_patterns"].return_value = policy
    gh_mocks["list_branch_policies"].return_value = []
    gh_mocks["create_branch_policy"].side_effect = [None, CommandExecutionError("quota exceeded")]

    with pytest.raises(CommandExecutionError, match="quota exceeded") as exc:
        sc_environments.present(
            MagicMock(), "release", "repo", deployment_branches=["br-a", "br-b"]
        )

    assert exc.value.changes == {"deployment_branches": {"added": ["br-a"]}}
    gh_mocks["set_"].assert_not_called()
