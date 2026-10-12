import pytest
from salt.exceptions import CommandExecutionError


def test_list_issues(github_repo):
    ret = github_repo.list_issues()
    # Only open issues by default, pull requests are excluded
    assert [issue["title"] for issue in ret] == ["Found a bug"]
    assert ret[0]["user"] == "user1"
    assert ret[0]["assignee"] == "user2"
    assert ret[0]["labels"] == ["bug", "prio:high"]
    assert ret[0]["milestone"] == "v1.0"


def test_list_issues_all(github_repo):
    ret = github_repo.list_issues(state="all")
    assert {issue["title"] for issue in ret} == {"Found a bug", "Stale issue"}


def test_list_issues_full_output(github_repo):
    ret = github_repo.list_issues(output="full")
    assert ret[0]["number"] == 1
    assert ret[0]["body"] == ""


def test_list_issues_missing_repo(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.list_issues(repo_name="ghost")


def test_get_issue(github_repo):
    ret = github_repo.get_issue(1)
    assert ret["title"] == "Found a bug"
    assert ret["issue_number"] == 1


def test_get_issue_full_output(github_repo):
    ret = github_repo.get_issue(1, output="full")
    assert ret["number"] == 1


def test_get_issue_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.get_issue(42)


def test_get_issue_comments(github_repo):
    ret = github_repo.get_issue_comments(1)
    assert len(ret) == 2
    assert {comment["user_login"] for comment in ret} == {"user1", "user2"}
    assert "body" not in ret[0]


def test_get_issue_comments_full_output(github_repo):
    ret = github_repo.get_issue_comments(1, output="full")
    assert {comment["body"] for comment in ret} == {"Working on it", "Thanks!"}
