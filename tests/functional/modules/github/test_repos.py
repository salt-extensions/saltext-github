import pytest
from salt.exceptions import CommandExecutionError

from tests.support.github import NotFound


def test_list_repos(github):
    assert set(github.list_repos()) == {"repo-a", "repo-b"}


def test_list_private_repos(github):
    assert github.list_private_repos() == ["repo-b"]


def test_list_public_repos(github):
    assert github.list_public_repos() == ["repo-a"]


def test_get_repo_info(github):
    ret = github.get_repo_info("repo-a")
    assert ret["name"] == "repo-a"
    assert ret["full_name"] == "testorg/repo-a"
    assert ret["description"] == "Test repo repo-a"
    assert ret["private"] is False
    assert ret["default_branch"] == "main"
    assert ret["has_issues"] is True


def test_get_repo_info_missing(github):
    with pytest.raises(CommandExecutionError):
        github.get_repo_info("ghost")


def test_get_repo_info_uses_cache(github, fake_org):
    assert github.get_repo_info("repo-a")["description"] == "Test repo repo-a"
    fake_org.get_repo("repo-a").data.description = "mutated"
    # Cached result is returned until the cache is bypassed
    assert github.get_repo_info("repo-a")["description"] == "Test repo repo-a"
    assert github.get_repo_info("repo-a", ignore_cache=True)["description"] == "mutated"


def test_list_repos_primes_repo_info_cache(github, fake_org):
    github.list_repos()
    fake_org.get_repo("repo-a").data.description = "mutated"
    assert github.get_repo_info("repo-a")["description"] == "Test repo repo-a"


def test_add_repo(github, fake_org):
    assert github.add_repo("new-repo", description="Brand new") is True
    assert fake_org.get_repo("new-repo").description == "Brand new"


def test_edit_repo(github, fake_org):
    assert github.edit_repo("repo-a", description="Updated") is True
    assert fake_org.get_repo("repo-a").description == "Updated"
    # edit_repo refreshes the cache itself
    assert github.get_repo_info("repo-a")["description"] == "Updated"


def test_edit_repo_privacy_guard(github):
    with pytest.raises(CommandExecutionError, match="privacy"):
        github.edit_repo("repo-a", private=True, profile="github_noprivacy")


def test_remove_repo(github, fake_org):
    assert github.remove_repo("repo-b") is True
    with pytest.raises(NotFound):
        fake_org.get_repo("repo-b")


def test_remove_repo_missing(github):
    assert github.remove_repo("ghost") is False


def test_remove_repo_failure(github, fake_org):
    # The repo vanishes server-side behind the module's cache
    github.list_repos()
    fake_org.remove_repo("repo-b")
    assert github.remove_repo("repo-b") is False


def test_add_repo_duplicate(github):
    # The API refuses to create a repo with an existing name
    assert github.add_repo("repo-a") is False


def test_edit_repo_missing(github):
    assert github.edit_repo("ghost", description="Nope") is False


def test_get_repo_teams(github):
    ret = github.get_repo_teams("repo-a")
    assert [team["name"] for team in ret] == ["Team A"]


def test_get_repo_teams_missing_repo(github):
    with pytest.raises(CommandExecutionError, match="could not be found"):
        github.get_repo_teams("ghost")
