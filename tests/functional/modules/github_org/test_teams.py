import pytest
from salt.exceptions import CommandExecutionError


def test_list_teams(github_org):
    ret = github_org.list_teams()
    assert set(ret) == {"Team A"}
    assert ret["Team A"]["slug"] == "team-a"


def test_list_teams_uses_cache(github_org, fake_org):
    assert set(github_org.list_teams()) == {"Team A"}
    fake_org.add_team("Team B")
    # Cached result is returned until the cache is bypassed
    assert "Team B" not in github_org.list_teams()
    assert "Team B" in github_org.list_teams(ignore_cache=True)


def test_get_team(github_org):
    ret = github_org.get_team("Team A")
    assert ret["name"] == "Team A"
    assert ret["slug"] == "team-a"
    assert ret["description"] == "Awesome Team: Team A"


def test_get_team_excludes_internal_caches(github_org):
    github_org.list_team_repos("Team A")
    github_org.list_team_members("Team A")
    ret = github_org.get_team("Team A")
    assert "repos" not in ret
    assert "members" not in ret


def test_get_team_by_slug(github_org):
    assert github_org.get_team("team-a")["name"] == "Team A"


def test_get_team_name_case_insensitive(github_org):
    assert github_org.get_team("team a")["name"] == "Team A"


def test_get_team_missing(github_org):
    with pytest.raises(CommandExecutionError, match="does not exist"):
        github_org.get_team("ghost")


def test_add_team(github_org, fake_org):
    ret = github_org.add_team("Team B", description="Team B", privacy="closed")
    # The created team's details are returned
    assert ret["slug"] == "team-b"
    assert ret["description"] == "Team B"
    assert fake_org.get_team("team-b").description == "Team B"
    # add_team refreshes the team cache itself
    assert github_org.get_team("Team B")


def test_add_team_with_repos(github_org, fake_org):
    assert github_org.add_team("Team B", repo_names=["testorg/repo-b"])["slug"] == "team-b"
    assert fake_org.get_team("team-b").repos["repo-b"] == "pull"


def test_add_team_duplicate(github_org):
    # The API refuses to create a team whose slug already exists
    with pytest.raises(CommandExecutionError):
        github_org.add_team("Team A")


def test_edit_team(github_org, fake_org):
    ret = github_org.edit_team(
        "Team A", description="Renovated", privacy="secret", permission="push"
    )
    # The refreshed team details are returned and the cache is updated
    assert ret["description"] == "Renovated"
    team = fake_org.get_team("team-a")
    assert team.description == "Renovated"
    assert team.privacy == "secret"
    assert team.permission == "push"
    assert github_org.get_team("Team A")["description"] == "Renovated"


def test_edit_team_missing(github_org):
    with pytest.raises(CommandExecutionError, match="does not exist"):
        github_org.edit_team("ghost", description="Nope")


def test_remove_team(github_org, fake_org):
    assert github_org.remove_team("Team A") is True
    assert "team-a" not in [team.slug for team in fake_org.teams]


def test_remove_team_missing(github_org):
    with pytest.raises(CommandExecutionError, match="does not exist"):
        github_org.remove_team("ghost")


def test_remove_team_stale_cache(github_org, fake_org):
    # A team known to the module cache but deleted on the server side
    github_org.list_teams()
    fake_org.remove_team("team-a")
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.remove_team("Team A")


def test_list_team_repos(github_org):
    ret = github_org.list_team_repos("Team A")
    assert list(ret) == ["repo-a"]
    assert ret["repo-a"]["permission"] == "pull"


def test_list_team_repos_missing_team(github_org):
    with pytest.raises(CommandExecutionError, match="does not exist"):
        github_org.list_team_repos("ghost")


def test_list_team_repos_uses_cache(github_org, fake_org):
    assert list(github_org.list_team_repos("Team A")) == ["repo-a"]
    fake_org.get_team("team-a").add_repo("repo-b", "admin")
    # Cached result is returned until the cache is bypassed
    assert list(github_org.list_team_repos("Team A")) == ["repo-a"]
    refreshed = github_org.list_team_repos("Team A", ignore_cache=True)
    assert set(refreshed) == {"repo-a", "repo-b"}
    assert refreshed["repo-b"]["permission"] == "admin"


def test_list_team_repos_fields(github_org):
    assert github_org.list_team_repos("Team A", fields="permission") == {"repo-a": "pull"}


def test_add_team_repo(github_org, fake_org):
    assert github_org.add_team_repo("repo-b", "Team A", permission="push") is True
    assert fake_org.get_team("team-a").repos["repo-b"] == "push"
    assert github_org.list_team_repos("Team A")["repo-b"]["permission"] == "push"


def test_add_team_repo_missing_team(github_org):
    with pytest.raises(CommandExecutionError, match="does not exist"):
        github_org.add_team_repo("repo-a", "ghost")


def test_add_team_repo_missing_repo(github_org):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.add_team_repo("ghost", "Team A")


def test_remove_team_repo(github_org, fake_org):
    assert github_org.remove_team_repo("repo-a", "Team A") is True
    assert "repo-a" not in fake_org.get_team("team-a").repos


def test_remove_team_repo_missing_repo(github_org):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.remove_team_repo("ghost", "Team A")


def test_list_team_members(github_org):
    assert github_org.list_team_members("Team A") == ["user1"]


def test_list_team_members_missing_team(github_org):
    with pytest.raises(CommandExecutionError, match="does not exist"):
        github_org.list_team_members("ghost")


def test_list_team_members_uses_cache(github_org, fake_org):
    assert github_org.list_team_members("Team A") == ["user1"]
    fake_org.get_team("team-a").add_member("user2")
    # Cached result is returned until the cache is bypassed
    assert github_org.list_team_members("Team A") == ["user1"]
    assert sorted(github_org.list_team_members("Team A", ignore_cache=True)) == ["user1", "user2"]


def test_is_team_member(github_org):
    assert github_org.is_team_member("user1", "Team A") is True
    assert github_org.is_team_member("user2", "Team A") is False


def test_add_team_member(github_org, fake_org):
    assert github_org.add_team_member("user2", "Team A") is True
    assert "user2" in fake_org.get_team("team-a").data.members


def test_add_team_member_missing_user(github_org):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.add_team_member("ghost", "Team A")


def test_remove_team_member(github_org, fake_org):
    assert github_org.remove_team_member("user1", "Team A") is True
    assert "user1" not in fake_org.get_team("team-a").members
