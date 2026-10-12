import pytest
from salt.exceptions import CommandExecutionError


def test_get_milestones_min_output(github):
    ret = github.get_milestones(repo_name="repo-a")
    assert len(ret) == 2
    for milestone in ret.values():
        # min output strips these keys and must not crash when absent
        assert "creator" not in milestone
        assert "html_url" not in milestone
        assert "labels_url" not in milestone
    assert sorted(milestone["title"] for milestone in ret.values()) == ["v1.0", "v2.0"]


def test_get_milestones_full_output(github):
    ret = github.get_milestones(repo_name="repo-a", output="full")
    assert all(milestone["creator"]["login"] == "user1" for milestone in ret.values())


def test_get_milestone_by_number(github):
    # repo_name defaults to the profile value (repo-a)
    ret = github.get_milestone(number=1)
    assert [milestone["title"] for milestone in ret.values()] == ["v1.0"]


def test_get_milestone_by_name(github):
    ret = github.get_milestone(name="v2.0", repo_name="repo-a")
    assert [milestone["title"] for milestone in ret.values()] == ["v2.0"]


def test_get_milestones_repo_name_from_profile(github):
    assert len(github.get_milestones()) == 2


def test_get_milestones_filter_args(github, fake_github):
    github.get_milestones(
        repo_name="repo-a", state="closed", sort="completeness", direction="desc", per_page=10
    )
    (req,) = fake_github.filter_requests(path="*/repo-a/milestones")
    for key, value in (
        ("state", "closed"),
        ("sort", "completeness"),
        ("direction", "desc"),
        ("per_page", "10"),
    ):
        assert req.query[key] == value


def test_get_milestones_missing_repo(github):
    with pytest.raises(CommandExecutionError, match="404"):
        github.get_milestones("ghost")


def test_get_milestone_by_number_full_output(github):
    ret = github.get_milestone(number=1, repo_name="repo-a", output="full")
    (milestone,) = ret.values()
    assert milestone["creator"]["login"] == "user1"


def test_get_milestone_by_number_missing(github):
    assert github.get_milestone(number=99, repo_name="repo-a") == {}


def test_get_milestone_by_name_missing(github):
    assert github.get_milestone(name="nope", repo_name="repo-a") == {}


def test_get_milestone_requires_name_or_number(github):
    with pytest.raises(CommandExecutionError, match="'name' or 'number'"):
        github.get_milestone(repo_name="repo-a")
