import pytest
from salt.exceptions import CommandExecutionError


@pytest.fixture
def repo_a(fake_org):
    return fake_org.get_repo("repo-a")


def test_get_issues(github, repo_a):
    bug = repo_a.issues["Found a bug"]
    pull = repo_a.pulls["Fix the bug"]
    ret = github.get_issues("repo-a")
    # Only open issues by default, and PRs listed by the API are filtered out
    assert set(ret) == {bug.id}
    assert pull.id not in ret
    formatted = ret[bug.id]
    assert formatted["issue_number"] == bug.number
    assert formatted["state"] == "open"
    assert formatted["title"] == "Found a bug"
    assert formatted["user"] == "user1"
    assert formatted["assignee"] == "user2"
    assert formatted["labels"] == ["bug", "prio:high"]
    assert formatted["milestone"] == "v1.0"


def test_get_issues_all_states(github, repo_a):
    ret = github.get_issues("repo-a", state="all")
    assert {issue["title"] for issue in ret.values()} == {"Found a bug", "Stale issue"}


def test_get_issues_full_output(github, repo_a):
    bug = repo_a.issues["Found a bug"]
    ret = github.get_issues("repo-a", output="full")
    assert ret[bug.id]["labels"] == [{"name": "bug"}, {"name": "prio:high"}]
    assert ret[bug.id]["user"]["login"] == "user1"


def test_get_issues_filter_args(github, fake_github, repo_a):
    bug = repo_a.issues["Found a bug"]
    ret = github.get_issues(
        "repo-a",
        milestone=1,
        assignee="user2",
        creator="user1",
        mentioned="user2",
        labels="bug",
        since="2026-01-01T00:00:00Z",
        sort="updated",
        direction="asc",
        per_page=10,
    )
    assert bug.id in ret
    (req,) = fake_github.filter_requests(path="*/repo-a/issues")
    for key, value in (
        ("milestone", "1"),
        ("assignee", "user2"),
        ("creator", "user1"),
        ("mentioned", "user2"),
        ("labels", "bug"),
        ("since", "2026-01-01T00:00:00Z"),
        ("sort", "updated"),
        ("direction", "asc"),
        ("per_page", "10"),
    ):
        assert req.query[key] == value


def test_get_issues_label_filter_mismatch(github):
    assert github.get_issues("repo-a", labels="nonexistent") == {}


def test_get_issues_repo_name_from_profile(github, repo_a):
    bug = repo_a.issues["Found a bug"]
    assert bug.id in github.get_issues()


def test_get_issues_missing_repo(github):
    with pytest.raises(CommandExecutionError, match="404"):
        github.get_issues("ghost")


def test_get_issue(github, repo_a):
    bug = repo_a.issues["Found a bug"]
    ret = github.get_issue(bug.number, repo_name="repo-a")
    assert set(ret) == {bug.id}
    assert ret[bug.id]["title"] == "Found a bug"
    assert ret[bug.id]["user"] == "user1"


def test_get_issue_full_output(github, repo_a):
    bug = repo_a.issues["Found a bug"]
    # repo_name defaults to the profile value (repo-a)
    ret = github.get_issue(bug.number, output="full")
    assert ret[bug.id]["user"]["login"] == "user1"


def test_get_issue_missing(github):
    assert github.get_issue(999, repo_name="repo-a") == {}


def test_get_issue_comments(github, repo_a):
    bug = repo_a.issues["Found a bug"]
    ret = github.get_issue_comments(bug.number, repo_name="repo-a")
    assert len(ret) == 2
    assert {comment["user_login"] for comment in ret.values()} == {"user1", "user2"}
    for comment_id, comment in ret.items():
        assert comment["id"] == comment_id


def test_get_issue_comments_since(github, repo_a):
    bug = repo_a.issues["Found a bug"]
    ret = github.get_issue_comments(bug.number, repo_name="repo-a", since="2026-10-11T14:30:00Z")
    assert [comment["user_login"] for comment in ret.values()] == ["user1"]


def test_get_issue_comments_full_output(github, repo_a):
    bug = repo_a.issues["Found a bug"]
    # repo_name defaults to the profile value (repo-a)
    ret = github.get_issue_comments(bug.number, output="full")
    assert {comment["body"] for comment in ret.values()} == {"Working on it", "Thanks!"}


def test_get_issue_comments_missing_issue(github):
    with pytest.raises(CommandExecutionError, match="404"):
        github.get_issue_comments(999, repo_name="repo-a")
