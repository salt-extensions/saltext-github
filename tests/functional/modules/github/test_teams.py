from tests.support.github import Team


def _raise_api_error(*args, **kwargs):
    raise RuntimeError("induced API failure")


def test_list_teams(github, fake_github):
    ret = github.list_teams()
    assert "Team A" in ret
    assert ret["Team A"]["slug"] == "team-a"
    assert ret["Team A"]["description"] == "Awesome Team: Team A"
    assert ret["Team A"]["privacy"] == "closed"
    assert ret["Team A"]["permission"] == "pull"
    # Rendering the team list must not trigger per-team completion requests
    assert [req.path for req in fake_github.requests] == [
        "/orgs/testorg",
        "/orgs/testorg/teams",
    ]


def test_list_teams_uses_cache(github, fake_org):
    assert "Team A" in github.list_teams()
    fake_org.add_team("Team B")
    # Cached result is returned until the cache is bypassed
    assert "Team B" not in github.list_teams()
    assert "Team B" in github.list_teams(ignore_cache=True)


def test_get_team(github):
    ret = github.get_team("Team A")
    assert ret
    assert ret["slug"] == "team-a"


def test_get_team_missing(github):
    assert not github.get_team("ghost")


def test_add_team(github, fake_org):
    assert github.add_team("Team B", description="Team B", privacy="closed") is True
    created = fake_org.get_team("team-b")
    assert created.description == "Team B"
    # add_team refreshes the team cache itself
    assert github.get_team("Team B")


def test_add_team_with_repos(github, fake_org):
    assert github.add_team("Team B", repo_names=["testorg/repo-b"]) is True
    assert fake_org.get_team("team-b").repos["repo-b"] == "pull"
    assert github.list_team_repos("Team B")["repo-b"]["permission"] == "pull"


def test_edit_team(github, fake_org):
    assert github.edit_team("Team A", description="Renovated") is True
    assert fake_org.get_team("team-a").description == "Renovated"


def test_remove_team(github, fake_org):
    assert "team-a" in [team.slug for team in fake_org.teams]
    assert github.remove_team("Team A") is True
    assert "team-a" not in [team.slug for team in fake_org.teams]


def test_remove_team_missing(github):
    assert github.remove_team("ghost") is False


def test_add_team_duplicate(github):
    # The API refuses to create a team whose slug already exists
    assert github.add_team("Team A") is False


def test_edit_team_missing(github):
    assert github.edit_team("ghost", description="Nope") is False


def test_edit_team_privacy_permission(github, fake_org):
    assert github.edit_team("Team A", privacy="secret", permission="push") is True
    team = fake_org.get_team("team-a")
    assert team.privacy == "secret"
    assert team.permission == "push"


def test_edit_team_stale_cache(github, fake_org):
    # A team known to the module cache but deleted on the server side
    github.list_teams()
    fake_org.remove_team("team-a")
    assert github.edit_team("Team A", description="Nope") is False


def test_remove_team_stale_cache(github, fake_org):
    github.list_teams()
    fake_org.remove_team("team-a")
    assert github.remove_team("Team A") is False


def test_list_team_repos(github):
    ret = github.list_team_repos("Team A")
    assert set(ret) == {"repo-a"}
    assert ret["repo-a"]["permission"] == "pull"


def test_add_team_repo(github, fake_org):
    assert github.add_team_repo("repo-b", "Team A", permission="push") is True
    assert fake_org.get_team("team-a").repos["repo-b"] == "push"
    assert github.list_team_repos("Team A")["repo-b"]["permission"] == "push"


def test_remove_team_repo(github, fake_org):
    assert github.remove_team_repo("repo-a", "Team A") is True
    assert "repo-a" not in fake_org.get_team("team-a").repos


def test_list_team_members(github):
    assert github.list_team_members("Team A") == ["user1"]


def test_is_team_member(github):
    assert github.is_team_member("user1", "Team A") is True
    assert github.is_team_member("user2", "Team A") is False


def test_add_team_member(github, fake_org):
    assert github.add_team_member("user2", "Team A") is True
    assert "user2" in fake_org.get_team("team-a").data.members


def test_remove_team_member(github, fake_org):
    assert github.remove_team_member("user1", "Team A") is True
    assert "user1" not in fake_org.get_team("team-a").members


def test_list_team_repos_missing_team(github):
    assert github.list_team_repos("ghost") is False


def test_list_team_repos_uses_cache(github, fake_org):
    assert set(github.list_team_repos("Team A")) == {"repo-a"}
    fake_org.get_team("team-a").add_repo("repo-b", "admin")
    # Cached result is returned until the cache is bypassed
    assert set(github.list_team_repos("Team A")) == {"repo-a"}
    refreshed = github.list_team_repos("Team A", ignore_cache=True)
    assert set(refreshed) == {"repo-a", "repo-b"}
    assert refreshed["repo-b"]["permission"] == "admin"


def test_list_team_repos_stale_cache(github, fake_org):
    # A team known to the module cache but deleted on the server side
    github.list_teams()
    fake_org.remove_team("team-a")
    assert github.list_team_repos("Team A") == {}


def test_list_team_members_missing_team(github):
    assert github.list_team_members("ghost") is False


def test_list_team_members_stale_cache(github, fake_org):
    github.list_teams()
    fake_org.remove_team("team-a")
    assert github.list_team_members("Team A") == []


def test_is_team_member_missing_team(github):
    assert github.is_team_member("user1", "ghost") is False


def test_list_team_members_uses_cache(github, fake_org):
    assert github.list_team_members("Team A") == ["user1"]
    fake_org.get_team("team-a").add_member("user2")
    # Cached result is returned until the cache is bypassed
    assert github.list_team_members("Team A") == ["user1"]
    assert sorted(github.list_team_members("Team A", ignore_cache=True)) == ["user1", "user2"]


def test_add_team_repo_missing_team(github):
    assert github.add_team_repo("repo-a", "ghost") is False


def test_add_team_repo_missing_repo(github):
    assert github.add_team_repo("ghost", "Team A") is False


def test_add_team_repo_api_failure(github, monkeypatch):
    # The fake responds with an error status when the operation raises
    monkeypatch.setattr(Team, "add_repo", _raise_api_error)
    assert github.add_team_repo("repo-b", "Team A", permission="push") is False


def test_remove_team_repo_missing_team(github):
    assert github.remove_team_repo("repo-a", "ghost") is False


def test_remove_team_repo_missing_repo(github):
    assert github.remove_team_repo("ghost", "Team A") is False


def test_add_team_member_missing_team(github):
    assert github.add_team_member("user1", "ghost") is False


def test_add_team_member_missing_user(github):
    assert github.add_team_member("ghost", "Team A") is False


def test_add_team_member_api_failure(github, monkeypatch):
    monkeypatch.setattr(Team, "add_member", _raise_api_error)
    assert github.add_team_member("user2", "Team A") is False


def test_remove_team_member_not_removed(github, monkeypatch):
    # The API reports success, but the member is still present afterwards
    monkeypatch.setattr(Team, "remove_member", lambda *args, **kwargs: None)
    assert github.remove_team_member("user1", "Team A") is False


def test_remove_team_member_missing_team(github):
    assert github.remove_team_member("user1", "ghost") is False


def test_remove_team_member_missing_user(github):
    assert github.remove_team_member("ghost", "Team A") is False


def test_list_members_without_mfa_uses_cache(github, fake_state):
    assert github.list_members_without_mfa() == ["user2"]
    fake_state.get_user("user1").data.two_factor_authentication = False
    # Cached result is returned until the cache is bypassed
    assert github.list_members_without_mfa() == ["user2"]
    assert sorted(github.list_members_without_mfa(ignore_cache=True)) == ["user1", "user2"]


def test_list_members_without_mfa(github, fake_github):
    assert github.list_members_without_mfa() == ["user2"]
    member_queries = [
        req.query["filter"] for req in fake_github.filter_requests(path="*/members", query="filter")
    ]
    assert "2fa_disabled" in member_queries
