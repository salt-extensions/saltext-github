import pytest
from salt.exceptions import CommandExecutionError


def test_get_info(github_repo):
    # repo_name defaults to the profile's repo-a
    ret = github_repo.get_info()
    assert ret["name"] == "repo-a"
    assert ret["full_name"] == "testorg/repo-a"
    assert ret["description"] == "Test repo repo-a"
    assert ret["private"] is False
    assert ret["default_branch"] == "main"


def test_get_info_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="could not be found"):
        github_repo.get_info(repo_name="ghost")


def test_get_info_uses_cache(github_repo, fake_org):
    assert github_repo.get_info()["description"] == "Test repo repo-a"
    fake_org.get_repo("repo-a").data.description = "mutated"
    # Cached result is returned until the cache is bypassed
    assert github_repo.get_info()["description"] == "Test repo repo-a"
    assert github_repo.get_info(ignore_cache=True)["description"] == "mutated"


def test_get_teams(github_repo):
    ret = github_repo.get_teams()
    assert [team["name"] for team in ret] == ["Team A"]


def test_get_teams_missing_repo(github_repo):
    with pytest.raises(CommandExecutionError, match="could not be found"):
        github_repo.get_teams(repo_name="ghost")


def test_update(github_repo, fake_org):
    ret = github_repo.update(description="Updated")
    # The refreshed repo information is returned
    assert ret["description"] == "Updated"
    assert fake_org.get_repo("repo-a").description == "Updated"
    assert github_repo.get_info()["description"] == "Updated"


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
