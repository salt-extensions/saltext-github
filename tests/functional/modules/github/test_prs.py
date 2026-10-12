import pytest
from salt.exceptions import CommandExecutionError


@pytest.fixture
def repo_a(fake_org):
    return fake_org.get_repo("repo-a")


def test_get_prs(github, repo_a):
    pull = repo_a.pulls["Fix the bug"]
    ret = github.get_prs("repo-a")
    assert set(ret) == {pull.id}
    formatted = ret[pull.id]
    assert formatted["pr_number"] == pull.number
    assert formatted["state"] == "open"
    assert formatted["title"] == "Fix the bug"
    assert formatted["user"] == "user2"
    assert formatted["base_branch"] == "main"


def test_get_prs_full_output(github, repo_a):
    pull = repo_a.pulls["Fix the bug"]
    ret = github.get_prs("repo-a", output="full")
    assert ret[pull.id]["head"]["ref"] == "bugfix"
    assert ret[pull.id]["user"]["login"] == "user2"


def test_get_prs_filter_args(github, fake_github, repo_a):
    pull = repo_a.pulls["Fix the bug"]
    ret = github.get_prs(
        "repo-a",
        state="all",
        head="testorg:bugfix",
        base="main",
        sort="updated",
        direction="asc",
        per_page=50,
    )
    assert pull.id in ret
    (req,) = fake_github.filter_requests(path="*/repo-a/pulls")
    for key, value in (
        ("state", "all"),
        ("head", "testorg:bugfix"),
        ("base", "main"),
        ("sort", "updated"),
        ("direction", "asc"),
        ("per_page", "50"),
    ):
        assert req.query[key] == value


def test_get_prs_repo_name_from_profile(github, repo_a):
    pull = repo_a.pulls["Fix the bug"]
    assert pull.id in github.get_prs()


def test_get_prs_missing_repo(github):
    with pytest.raises(CommandExecutionError, match="404"):
        github.get_prs("ghost")
