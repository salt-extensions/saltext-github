import pytest
from salt.exceptions import CommandExecutionError


def test_list_labels(github_repo):
    ret = github_repo.list_labels()
    assert [label["name"] for label in ret] == ["bug"]


def test_get_label(github_repo):
    ret = github_repo.get_label("bug")
    assert ret["color"] == "d73a4a"
    assert ret["description"] == "Something is broken"


def test_get_label_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.get_label("ghost")


def test_get_label_special_chars(github_repo, fake_org):
    # Label names are URL-quoted on the wire
    fake_org.get_repo("repo-a").add_label("prio: high", color="ff0000")
    ret = github_repo.get_label("prio: high")
    assert ret["name"] == "prio: high"


def test_add_label(github_repo, fake_org):
    ret = github_repo.add_label("release", color="#00FF00", description="Release automation")
    assert ret["name"] == "release"
    label = fake_org.get_repo("repo-a").get_label("release")
    # The color is normalized before submission
    assert label.color == "00ff00"
    assert label.description == "Release automation"


def test_edit_label(github_repo, fake_org):
    github_repo.edit_label("bug", color="ff0000")
    label = fake_org.get_repo("repo-a").get_label("bug")
    assert label.color == "ff0000"
    assert label.description == "Something is broken"


def test_edit_label_rename(github_repo, fake_org):
    github_repo.edit_label("bug", new_name="defect")
    repo = fake_org.get_repo("repo-a")
    assert "defect" in repo.labels
    assert "bug" not in repo.labels


def test_remove_label(github_repo, fake_org):
    assert github_repo.remove_label("bug") is True
    assert "bug" not in fake_org.get_repo("repo-a").labels


def test_remove_label_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.remove_label("ghost")
