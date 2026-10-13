import pytest

from tests.support.github import NotFound


def test_team_present_create(github_org, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_org.team_present(
        name="team-b", description="Team B", privacy="closed", members=["user1"], test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes["created"] == "team-b"
    # member additions are projected even for new teams
    assert ret.changes["members_added"] == ["user1"]
    if testmode:
        assert "would have been created" in ret.comment
        assert "team-b" not in fake_org.teams
    else:
        created = fake_org.get_team("team-b")
        assert set(created.data.members) == {"user1"}


def test_team_present_idempotent(github_org, fake_github, testmode):
    ret = github_org.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="closed",
        permission="pull",
        members=["user1"],
        test=testmode,
    )
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_team_present_unspecified_settings_unmanaged(github_org, fake_github, testmode):
    # Without explicit privacy/permission/members/repo_names, only
    # existence is ensured
    ret = github_org.team_present(name="Team A", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_team_present_converges_drift(github_org, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_org.team_present(
        name="Team A",
        description="Updated A",
        privacy="closed",
        permission="pull",
        members=["user2"],
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes["old"] == {"description": "Awesome Team: Team A"}
    assert ret.changes["new"] == {"description": "Updated A"}
    assert ret.changes["members_added"] == ["user2"]
    assert ret.changes["members_removed"] == ["user1"]
    team = fake_org.get_team("team-a")
    if testmode:
        assert "would have been updated" in ret.comment
        assert team.description == "Awesome Team: Team A"
        assert set(team.data.members) == {"user1"}
    else:
        assert team.description == "Updated A"
        assert set(team.data.members) == {"user2"}

        rerun = github_org.team_present(
            name="Team A",
            description="Updated A",
            privacy="closed",
            permission="pull",
            members=["user2"],
        )
        assert rerun.result is True
        assert not rerun.changes


def test_team_present_permission_privacy_drift(github_org, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_org.team_present(name="Team A", privacy="secret", permission="push", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes["old"] == {"privacy": "closed", "permission": "pull"}
    assert ret.changes["new"] == {"privacy": "secret", "permission": "push"}
    team = fake_org.get_team("team-a")
    if testmode:
        assert team.permission == "pull"
        assert team.privacy == "closed"
    else:
        assert team.permission == "push"
        assert team.privacy == "secret"


def test_team_present_name_case_insensitive(github_org, fake_github, testmode):
    # "team a" resolves to the existing "Team A" since team identity
    # (the slug) is case-insensitive
    ret = github_org.team_present(name="team a", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_team_present_manages_repos(github_org, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_org.team_present(name="Team A", repo_names=["repo-b"], test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes["repos_added"] == ["repo-b"]
    assert ret.changes["repos_removed"] == ["repo-a"]
    team = fake_org.get_team("team-a")
    if testmode:
        assert "would have been updated" in ret.comment
        assert "repo-a" in team.repos
        assert "repo-b" not in team.repos
    else:
        assert "repo-b" in team.repos
        assert "repo-a" not in team.repos


def test_team_present_repos_case_insensitive(github_org, fake_github, testmode):
    # Repository names are compared case-insensitively
    ret = github_org.team_present(name="Team A", repo_names=["Repo-A"], test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_team_present_add_repo_failure(github_org):
    ret = github_org.team_present(name="Team A", repo_names=["ghost"])
    assert ret.result is False
    assert not ret.changes
    assert "Not Found" in ret.comment


def test_team_present_add_member_failure(github_org):
    ret = github_org.team_present(name="Team A", members=["user1", "ghost"])
    assert ret.result is False
    assert not ret.changes
    assert "Not Found" in ret.comment


def test_team_absent(github_org, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_org.team_absent(name="Team A", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes == {"deleted": "Team A"}
    if testmode:
        assert "would have been deleted" in ret.comment
        fake_org.get_team("team-a")
    else:
        with pytest.raises(NotFound):
            fake_org.get_team("team-a")

        rerun = github_org.team_absent(name="Team A")
        assert rerun.result is True
        assert not rerun.changes
