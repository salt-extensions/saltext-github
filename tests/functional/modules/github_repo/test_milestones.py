import pytest
from salt.exceptions import CommandExecutionError


def test_list_milestones(github_repo):
    ret = github_repo.list_milestones()
    assert [milestone["title"] for milestone in ret] == ["v1.0", "v2.0"]
    # min output drops presentation fields
    assert "creator" not in ret[0]


def test_list_milestones_full_output(github_repo):
    ret = github_repo.list_milestones(output="full")
    assert ret[0]["creator"]["login"] == "user1"


def test_get_milestone_by_number(github_repo):
    ret = github_repo.get_milestone(1)
    assert ret["title"] == "v1.0"


def test_get_milestone_by_name(github_repo):
    ret = github_repo.get_milestone(name="v2.0")
    assert ret["title"] == "v2.0"


def test_get_milestone_missing_number(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.get_milestone(42)


def test_get_milestone_missing_name(github_repo):
    with pytest.raises(CommandExecutionError, match="was not found"):
        github_repo.get_milestone(name="ghost")


def test_get_milestone_requires_identifier(github_repo):
    with pytest.raises(CommandExecutionError, match="'name' or 'number'"):
        github_repo.get_milestone()
