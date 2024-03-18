from unittest import mock

import pytest
import salt.modules.config as config_module
import saltext.github.states.github as github_state


@pytest.fixture
def configure_loader_modules():
    return {
        github_state: {
            "__salt__": {
                "github.list_rulesets": mock.MagicMock(return_value=None),
                "github.delete_ruleset": mock.MagicMock(return_value=None),
                "github.get_ruleset": mock.MagicMock(return_value=None),
                "github.update_ruleset": mock.MagicMock(return_value=None),
                "github.add_ruleset": mock.MagicMock(return_value=None),
            },
            "__opts__": {"test": False},
        },
        config_module: {
            "__salt__": {"config.option": config_module.option},
            "__opts__": {"test_ruleset": {"ruleset_type": "mocked_value"}},
        },
    }


def test_repo_absent_no_changes():
    # test list rulesets are None
    expected = {
        "name": "mock_repo_absent",
        "changes": {},
        "result": True,
        "comment": "Ruleset mock_repo_absent does not exist",
    }

    ret = github_state.ruleset_absent(
        name="mock_repo_absent",
        ruleset_type="repo",
        profile="test_ruleset",
        owner="mock",
        repo_name="mock_repo",
    )
    assert ret == expected

    # test list rulesets are returned but ruleset to be deleted is not listed
    mock_query = mock.MagicMock(return_value=[{"name": "mocked_repo_absent"}])

    with mock.patch.dict(github_state.__salt__, {"github.list_rulesets": mock_query}):
        ret = github_state.ruleset_absent(
            name="mock_repo_absent",
            ruleset_type="repo",
            profile="test_ruleset",
            owner="mock",
            repo_name="mock_repo",
        )
    assert ret == expected

    # test mode
    expected["result"] = None

    with mock.patch.dict(github_state.__opts__, {"test": True}):
        ret = github_state.ruleset_absent(
            name="mock_repo_absent",
            ruleset_type="repo",
            profile="test_ruleset",
            owner="mock",
            repo_name="mock_repo",
        )
        assert ret == expected


def test_repo_absent_changes():

    expected = {
        "name": "mock_repo_absent",
        "changes": {
            "old": "ruleset mock_repo_absent exists",
            "new": "ruleset mock_repo_absent deleted",
        },
        "result": True,
        "comment": "Deleted ruleset mock_repo_absent",
    }

    mock_query = mock.MagicMock(return_value=[{"name": "mock_repo_absent", "id": 1}])
    mock_delete = mock.MagicMock(return_value={"comment": "ruleset 1 successfully deleted"})

    with mock.patch.dict(
        github_state.__salt__,
        {"github.list_rulesets": mock_query, "github.delete_ruleset": mock_delete},
    ):
        ret = github_state.ruleset_absent(
            name="mock_repo_absent",
            ruleset_type="repo",
            profile="test_ruleset",
            owner="mock",
            repo_name="mock_repo",
        )
        assert ret == expected

    # test mode
    expected = {
        "name": "mock_repo_absent",
        "changes": {},
        "result": None,
        "comment": "Ruleset mock_repo_absent will be deleted",
    }

    mock_query = mock.MagicMock(return_value=[{"name": "mock_repo_absent", "id": 1}])
    mock_delete = mock.MagicMock(return_value={"comment": "ruleset 1 successfully deleted"})

    with mock.patch.dict(github_state.__opts__, {"test": True}):
        with mock.patch.dict(
            github_state.__salt__,
            {"github.list_rulesets": mock_query, "github.delete_ruleset": mock_delete},
        ):
            ret = github_state.ruleset_absent(
                name="mock_repo_absent",
                ruleset_type="repo",
                profile="test_ruleset",
                owner="mock",
                repo_name="mock_repo",
            )
            assert ret == expected


def test_repo_present_no_changes():
    # Test mode
    expected = {
        "name": "mock_repo_absent",
        "changes": {},
        "result": None,
        "comment": "ruleset present",
    }

    mock_query = mock.MagicMock(return_value=[{"name": "mock_repo_absent", "id": 1}])
    mock_ruleset = mock.MagicMock(return_value={"name": "mock_repo_absent", "id": 1})

    with mock.patch.dict(github_state.__opts__, {"test": True}):
        with mock.patch.dict(
            github_state.__salt__,
            {"github.list_rulesets": mock_query, "github.get_ruleset": mock_ruleset},
        ):
            ret = github_state.ruleset_present(
                name="mock_repo_absent",
                ruleset_type="repo",
                profile="test_ruleset",
                owner="mock",
                repo_name="mock_repo",
                ruleset_params={},
            )
            assert ret == expected

    expected["result"] = True

    with mock.patch.dict(
        github_state.__salt__,
        {"github.list_rulesets": mock_query, "github.get_ruleset": mock_ruleset},
    ):
        ret = github_state.ruleset_present(
            name="mock_repo_absent",
            ruleset_type="repo",
            profile="test_ruleset",
            owner="mock",
            repo_name="mock_repo",
            ruleset_params={},
        )
        assert ret == expected


def test_repo_present_update_ruleset():
    expected = {
        "name": "mock_repo_absent",
        "changes": {
            "old": "Ruleset properties were {'name': 'mock_repo_absent', 'id': 1, 'target': 'branch'}",
            "new": "Ruleset properties (that changed) are {'target': 'tag', 'name': 'mock_repo_absent'}",
        },
        "result": True,
        "comment": "ruleset updated",
    }

    mock_query = mock.MagicMock(return_value=[{"name": "mock_repo_absent", "id": 1}])
    mock_ruleset = mock.MagicMock(
        return_value={"name": "mock_repo_absent", "id": 1, "target": "branch"}
    )
    mock_update = mock.MagicMock(
        return_value={"name": "mock_repo_absent", "id": 1, "target": "tag"}
    )

    with mock.patch.dict(
        github_state.__salt__,
        {
            "github.list_rulesets": mock_query,
            "github.get_ruleset": mock_ruleset,
            "github.update_ruleset": mock_update,
        },
    ):
        ret = github_state.ruleset_present(
            name="mock_repo_absent",
            ruleset_type="repo",
            profile="test_ruleset",
            owner="mock",
            repo_name="mock_repo",
            ruleset_params={"target": "tag"},
        )
        assert ret == expected

    # Test mode
    expected = {
        "name": "mock_repo_absent",
        "changes": {},
        "result": None,
        "comment": "ruleset will be updated",
    }

    with mock.patch.dict(
        github_state.__salt__,
        {
            "github.list_rulesets": mock_query,
            "github.get_ruleset": mock_ruleset,
            "github.update_ruleset": mock_update,
        },
    ):
        with mock.patch.dict(github_state.__opts__, {"test": True}):
            ret = github_state.ruleset_present(
                name="mock_repo_absent",
                ruleset_type="repo",
                profile="test_ruleset",
                owner="mock",
                repo_name="mock_repo",
                ruleset_params={"target": "tag"},
            )
        assert ret == expected


def test_repo_present_add_ruleset():

    expected = {
        "name": "mock_repo_absent",
        "changes": {"old": "No existing ruleset found", "new": "Ruleset created"},
        "result": True,
        "comment": "ruleset added",
    }

    mock_query = mock.MagicMock(return_value=[])
    mock_add = mock.MagicMock(
        return_value={"name": "mock_repo_absent", "id": 1, "enforcement": "disabled"}
    )

    with mock.patch.dict(
        github_state.__salt__, {"github.list_rulesets": mock_query, "github.add_ruleset": mock_add}
    ):
        ret = github_state.ruleset_present(
            name="mock_repo_absent",
            ruleset_type="repo",
            profile="test_ruleset",
            owner="mock",
            repo_name="mock_repo",
            ruleset_params={"enforcement": "disabled"},
        )
        assert ret == expected

    # Test mode
    expected["result"] = None
    expected["comment"] = "ruleset will be added"
    expected["changes"] = {}

    with mock.patch.dict(github_state.__opts__, {"test": True}):
        with mock.patch.dict(
            github_state.__salt__,
            {"github.list_rulesets": mock_query, "github.add_ruleset": mock_add},
        ):
            ret = github_state.ruleset_present(
                name="mock_repo_absent",
                ruleset_type="repo",
                profile="test_ruleset",
                owner="mock",
                repo_name="mock_repo",
                ruleset_params={"enforcement": "disabled"},
            )
            assert ret == expected
