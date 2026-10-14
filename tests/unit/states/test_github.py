from unittest import mock

import pytest

from saltext.github.states import github as github_mod

RULESET_KWARGS = {
    "name": "mock_ruleset",
    "ruleset_type": "repo",
    "profile": "test_ruleset",
    "owner": "mock",
    "repo_name": "mock_repo",
}


@pytest.fixture(params=(False, True))
def testmode(request):
    return request.param


@pytest.fixture
def configure_loader_modules(testmode):
    return {
        github_mod: {
            "__salt__": {
                "github.list_rulesets": mock.MagicMock(return_value=None),
                "github.delete_ruleset": mock.MagicMock(return_value=None),
                "github.get_ruleset": mock.MagicMock(return_value=None),
                "github.update_ruleset": mock.MagicMock(return_value=None),
                "github.add_ruleset": mock.MagicMock(return_value=None),
            },
            "__opts__": {"test": testmode},
        },
    }


@pytest.mark.parametrize("existing", ([], [{"name": "other_ruleset"}]))
@pytest.mark.usefixtures("testmode")
def test_ruleset_absent_no_changes(existing):
    github_mod.__salt__["github.list_rulesets"].return_value = {"rulesets": existing}

    ret = github_mod.ruleset_absent(**RULESET_KWARGS)

    assert ret["result"] is True
    assert not ret["changes"]
    assert ret["comment"] == "Ruleset mock_ruleset does not exist"
    github_mod.__salt__["github.delete_ruleset"].assert_not_called()


def test_ruleset_absent_changes(testmode):
    github_mod.__salt__["github.list_rulesets"].return_value = {
        "rulesets": [{"name": "mock_ruleset", "id": 1}]
    }
    github_mod.__salt__["github.delete_ruleset"].return_value = {
        "comment": "ruleset 1 successfully deleted"
    }

    ret = github_mod.ruleset_absent(**RULESET_KWARGS)

    assert ret["result"] is (None if testmode else True)
    assert ret["changes"] == {
        "old": "ruleset mock_ruleset exists",
        "new": "ruleset mock_ruleset deleted",
    }
    assert ret["comment"] == (
        "Ruleset mock_ruleset will be deleted" if testmode else "Deleted ruleset mock_ruleset"
    )
    assert github_mod.__salt__["github.delete_ruleset"].called is not testmode


@pytest.mark.usefixtures("testmode")
def test_ruleset_present_no_changes():
    github_mod.__salt__["github.list_rulesets"].return_value = {
        "rulesets": [{"name": "mock_ruleset", "id": 1}]
    }
    github_mod.__salt__["github.get_ruleset"].return_value = {"name": "mock_ruleset", "id": 1}

    ret = github_mod.ruleset_present(**RULESET_KWARGS, ruleset_params={})

    assert ret["result"] is True
    assert not ret["changes"]
    assert ret["comment"] == "ruleset present"
    github_mod.__salt__["github.update_ruleset"].assert_not_called()
    github_mod.__salt__["github.add_ruleset"].assert_not_called()


def test_ruleset_present_update_ruleset(testmode):
    github_mod.__salt__["github.list_rulesets"].return_value = {
        "rulesets": [{"name": "mock_ruleset", "id": 1}]
    }
    github_mod.__salt__["github.get_ruleset"].return_value = {
        "name": "mock_ruleset",
        "id": 1,
        "target": "branch",
    }
    github_mod.__salt__["github.update_ruleset"].return_value = {
        "name": "mock_ruleset",
        "id": 1,
        "target": "tag",
    }

    ret = github_mod.ruleset_present(**RULESET_KWARGS, ruleset_params={"target": "tag"})

    assert ret["result"] is (None if testmode else True)
    assert ret["changes"] == {"old": {"target": "branch"}, "new": {"target": "tag"}}
    assert ret["comment"] == ("ruleset will be updated" if testmode else "ruleset updated")
    assert github_mod.__salt__["github.update_ruleset"].called is not testmode


def test_ruleset_present_add_ruleset(testmode):
    github_mod.__salt__["github.list_rulesets"].return_value = {"rulesets": None}
    github_mod.__salt__["github.add_ruleset"].return_value = {
        "name": "mock_ruleset",
        "id": 1,
        "enforcement": "disabled",
    }

    ret = github_mod.ruleset_present(**RULESET_KWARGS, ruleset_params={"enforcement": "disabled"})

    assert ret["result"] is (None if testmode else True)
    assert ret["changes"] == {"old": "No existing ruleset found", "new": "Ruleset created"}
    assert ret["comment"] == ("ruleset will be added" if testmode else "ruleset added")
    assert github_mod.__salt__["github.add_ruleset"].called is not testmode
