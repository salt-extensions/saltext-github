import pytest
from salt.exceptions import CommandExecutionError


def test_info(github_repo):
    # repo_name defaults to the profile's repo-a
    ret = github_repo.info()
    assert ret["name"] == "repo-a"
    assert ret["full_name"] == "testorg/repo-a"
    assert ret["description"] == "Test repo repo-a"
    assert ret["private"] is False
    assert ret["default_branch"] == "main"


def test_info_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="could not be found"):
        github_repo.info(repo_name="ghost")


def test_info_uses_cache(github_repo, fake_org):
    assert github_repo.info()["description"] == "Test repo repo-a"
    fake_org.get_repo("repo-a").data.description = "mutated"
    # Cached result is returned until the cache is bypassed
    assert github_repo.info()["description"] == "Test repo repo-a"
    assert github_repo.info(ignore_cache=True)["description"] == "mutated"


def test_get_teams(github_repo):
    ret = github_repo.get_teams()
    assert list(ret) == ["Team A"]
    assert ret["Team A"]["permission"] == "pull"


def test_get_teams_missing_repo(github_repo):
    with pytest.raises(CommandExecutionError, match="could not be found"):
        github_repo.get_teams(repo_name="ghost")


def test_update(github_repo, fake_org):
    ret = github_repo.update(description="Updated")
    # The refreshed repo information is returned
    assert ret["description"] == "Updated"
    assert fake_org.get_repo("repo-a").description == "Updated"
    assert github_repo.info()["description"] == "Updated"


def test_update_default_branch(github_repo, fake_org):
    ret = github_repo.update(default_branch="develop")
    assert ret["default_branch"] == "develop"
    assert fake_org.get_repo("repo-a").default_branch == "develop"


def test_update_privacy_guard(github_repo):
    with pytest.raises(CommandExecutionError, match="privacy"):
        github_repo.update(private=True, profile="github_noprivacy")


def test_update_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.update(repo_name="ghost", description="Nope")


def test_delete(github_repo, fake_org):
    assert github_repo.delete(repo_name="repo-b") is True
    assert "repo-b" not in fake_org.repos


def test_delete_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.delete(repo_name="ghost")


def test_list(github_repo):
    ret = github_repo.list()
    assert set(ret) == {"repo-a", "repo-b"}
    # Full repository details are included
    assert ret["repo-a"]["full_name"] == "testorg/repo-a"


def test_list_fields(github_repo):
    ret = github_repo.list(fields=["private"])
    assert ret == {"repo-a": {"private": False}, "repo-b": {"private": True}}
    # A single field name implodes the entries to its values
    assert github_repo.list(fields="private") == {"repo-a": False, "repo-b": True}


def test_list_unknown_field(github_repo):
    with pytest.raises(CommandExecutionError, match="Unknown field"):
        github_repo.list(fields="bogus")


def test_list_private_filter(github_repo):
    assert list(github_repo.list(private=True)) == ["repo-b"]
    assert list(github_repo.list(private=False)) == ["repo-a"]


def test_list_uses_cache(github_repo, fake_org):
    assert set(github_repo.list()) == {"repo-a", "repo-b"}
    fake_org.add_repo("repo-c")
    # Cached result is returned until the cache is bypassed
    assert set(github_repo.list()) == {"repo-a", "repo-b"}
    assert "repo-c" in github_repo.list(ignore_cache=True)


def test_create(github_repo, fake_org):
    ret = github_repo.create("new-repo", description="Brand new")
    assert ret["name"] == "new-repo"
    assert ret["description"] == "Brand new"
    assert fake_org.get_repo("new-repo").description == "Brand new"


def test_create_refreshes_caches(github_repo):
    assert set(github_repo.list()) == {"repo-a", "repo-b"}
    github_repo.create("new-repo", description="Brand new")
    # Both the repo list and single-repo caches know the new repo
    assert "new-repo" in github_repo.list()
    assert github_repo.info(repo_name="new-repo")["description"] == "Brand new"


def test_create_duplicate(github_repo):
    # The API refuses to create a repo with an existing name
    with pytest.raises(CommandExecutionError):
        github_repo.create("repo-a")
