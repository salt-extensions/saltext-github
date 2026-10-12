import pytest
from salt.exceptions import CommandExecutionError


def test_list_repos(github_org):
    assert set(github_org.list_repos()) == {"repo-a", "repo-b"}


def test_list_repos_private_filter(github_org):
    assert github_org.list_repos(private=True) == ["repo-b"]
    assert github_org.list_repos(private=False) == ["repo-a"]


def test_add_repo(github_org, fake_org):
    ret = github_org.add_repo("new-repo", description="Brand new")
    assert ret["name"] == "new-repo"
    assert ret["description"] == "Brand new"
    assert fake_org.get_repo("new-repo").description == "Brand new"


def test_add_repo_refreshes_caches(github_org, modules):
    assert set(github_org.list_repos()) == {"repo-a", "repo-b"}
    github_org.add_repo("new-repo", description="Brand new")
    # Both the repo list and single-repo caches know the new repo
    assert "new-repo" in github_org.list_repos()
    assert modules.github_repo.get_info(repo_name="new-repo")["description"] == "Brand new"


def test_add_repo_duplicate(github_org):
    # The API refuses to create a repo with an existing name
    with pytest.raises(CommandExecutionError):
        github_org.add_repo("repo-a")
