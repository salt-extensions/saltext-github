import pytest

from tests.support.github import NotFound


def test_team_present_create(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.team_present(
        name="team-b", description="Team B", privacy="closed", members={"user1": {}}, test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert "team" in ret.changes
    if testmode:
        # member changes are not projected for new teams
        assert "set to be created" in ret.comment
        assert "team-b" not in fake_org.teams
    else:
        assert "user1" in ret.changes
        created = fake_org.get_team("team-b")
        assert set(created.data.members) == {"user1"}


def test_team_present_idempotent(github, testmode):
    ret = github.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="closed",
        permission="pull",
        members={"user1": {}},
        test=testmode,
    )
    assert ret.result is True
    assert not ret.changes


def test_team_present_converges_drift(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.team_present(
        name="Team A",
        description="Updated A",
        privacy="closed",
        permission="pull",
        members={"user2": {}},
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert "team" in ret.changes
    assert "user1" in ret.changes  # removed (managed members)
    assert "user2" in ret.changes  # added
    team = fake_org.get_team("team-a")
    if testmode:
        assert "set to be edited" in ret.comment
        assert "User user2 set to be added" in ret.comment
        assert "User user1 set to be removed" in ret.comment
        assert team.description == "Awesome Team: Team A"
        assert set(team.data.members) == {"user1"}
    else:
        assert team.description == "Updated A"
        assert set(team.data.members) == {"user2"}


def test_team_present_permission_privacy_drift(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="secret",
        permission="push",
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert "team" in ret.changes
    team = fake_org.get_team("team-a")
    if testmode:
        assert team.permission == "pull"
        assert team.privacy == "closed"
    else:
        assert team.permission == "push"
        assert team.privacy == "secret"


def test_team_present_create_failure(github):
    # "team a" is not in the team cache (keyed by name), but its slug
    # collides with the existing "Team A" on creation
    ret = github.team_present(name="team a")
    assert ret.result is False
    assert "Failed to create team" in ret.comment


def test_team_present_manages_repos(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="closed",
        repo_names=["repo-b"],
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert "repo-b" in ret.changes  # added
    assert "repo-a" in ret.changes  # removed (not listed)
    team = fake_org.get_team("team-a")
    if testmode:
        assert "repos added" in ret.comment
        assert "repos removed" in ret.comment
        assert "repo-a" in team.repos
        assert "repo-b" not in team.repos
    else:
        assert "repo-b" in team.repos
        assert "repo-a" not in team.repos


def test_team_present_add_repo_failure(github):
    ret = github.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="closed",
        repo_names=["ghost"],
    )
    assert ret.result is False
    assert "Failed to add repo ghost" in ret.comment


def test_team_present_add_member_failure(github):
    ret = github.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="closed",
        members={"user1": {}, "ghost": {}},
    )
    assert ret.result is False
    assert "Failed to add user ghost" in ret.comment


def test_team_present_enforce_mfa_blocks_addition(github, fake_github, fake_org, testmode):
    # user2 has no MFA and is not in the team: they are not added, which
    # test mode explains in a comment
    before = len(fake_github.mutations())
    ret = github.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="closed",
        permission="pull",
        members={"user1": {}, "user2": {}},
        enforce_mfa=True,
        test=testmode,
    )
    assert ret.result is True  # nothing else changes in either mode
    assert len(fake_github.mutations()) == before
    assert set(fake_org.get_team("team-a").data.members) == {"user1"}
    assert ("will not be added to the team because they do not have MFA" in ret.comment) is testmode


def test_team_present_enforce_mfa_removal(github, fake_github, fake_org, testmode):
    # user2 has no MFA and is already in the team
    fake_org.get_team("team-a").add_member("user2")
    before = len(fake_github.mutations())
    ret = github.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="closed",
        permission="pull",
        members={"user1": {}, "user2": {}},
        enforce_mfa=True,
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert "due to MFA violation" in ret.changes["user2"]["new"]
    team = fake_org.get_team("team-a")
    if testmode:
        assert "set to be removed from the team because they do not have MFA" in ret.comment
        assert "user2" in team.members
    else:
        assert "user2" not in team.members


def test_team_present_mfa_exempt_member(github, fake_org):
    # mfa_exempt members are added even when MFA is enforced
    ret = github.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="closed",
        members={"user1": {}, "user2": {"mfa_exempt": True}},
        enforce_mfa=True,
    )
    assert ret.result is True
    assert "user2" in ret.changes
    assert "user2" in fake_org.get_team("team-a").members


def test_team_absent(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.team_absent(name="Team A", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes == {"old": "Team Team A exists", "new": "Team Team A deleted"}
    if testmode:
        assert "will be deleted" in ret.comment
        fake_org.get_team("team-a")
    else:
        with pytest.raises(NotFound):
            fake_org.get_team("team-a")

        rerun = github.team_absent(name="Team A")
        assert rerun.result is True
        assert not rerun.changes
