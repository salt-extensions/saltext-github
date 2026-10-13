import pytest
from salt.exceptions import CommandExecutionError


def test_list_issues(github_repo):
    ret = github_repo.list_issues()
    # Only open issues by default, pull requests are excluded
    assert [issue["title"] for issue in ret] == ["Found a bug"]
    assert ret[0]["number"] == 1
    assert ret[0]["user"]["login"] == "user1"
    assert ret[0]["assignee"]["login"] == "user2"
    assert [label["name"] for label in ret[0]["labels"]] == ["bug", "prio:high"]
    assert ret[0]["milestone"]["title"] == "v1.0"


def test_list_issues_fields(github_repo):
    assert github_repo.list_issues(fields="title") == ["Found a bug"]
    assert github_repo.list_issues(fields=["number", "title"]) == [
        {"number": 1, "title": "Found a bug"}
    ]


def test_list_issues_unknown_field(github_repo):
    with pytest.raises(CommandExecutionError, match="Unknown field"):
        github_repo.list_issues(fields="bogus")


def test_list_issues_all(github_repo):
    ret = github_repo.list_issues(state="all")
    assert {issue["title"] for issue in ret} == {"Found a bug", "Stale issue"}


def test_list_issues_missing_repo(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.list_issues(repo_name="ghost")


def test_get_issue(github_repo):
    ret = github_repo.get_issue(1)
    assert ret["title"] == "Found a bug"
    assert ret["number"] == 1


def test_get_issue_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.get_issue(42)


def test_get_issue_comments(github_repo):
    ret = github_repo.get_issue_comments(1)
    assert len(ret) == 2
    assert {comment["user"]["login"] for comment in ret} == {"user1", "user2"}
    assert {comment["body"] for comment in ret} == {"Working on it", "Thanks!"}
