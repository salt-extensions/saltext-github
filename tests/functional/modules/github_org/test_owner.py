"""
Verify that all functions can manage another organization via the
``owner`` argument.
"""

import pytest
from salt.exceptions import CommandExecutionError


def test_list_members_owner(github_org):
    assert github_org.list_members(owner="otherorg") == ["user2"]
    assert set(github_org.list_members()) == {"user1", "user2"}


def test_get_member_owner(github_org):
    assert github_org.get_member("user2", owner="otherorg")["in_org"] is True
    assert github_org.get_member("user1", owner="otherorg")["in_org"] is False


def test_add_member_owner(github_org, fake_state):
    # Invitations result in a pending membership
    assert github_org.add_member("newuser", owner="otherorg") is True
    member = fake_state.get_org("otherorg").get_member("newuser")
    assert member.state == "pending"
    assert "newuser" not in fake_state.get_org("testorg").members


def test_remove_member_owner(github_org, fake_state):
    assert github_org.remove_member("user2", owner="otherorg") is True
    assert "user2" not in fake_state.get_org("otherorg").members
    assert "user2" in fake_state.get_org("testorg").members


def test_org_rulesets_owner(github_org, fake_state):
    other_org = fake_state.get_org("otherorg")
    created = github_org.add_ruleset(
        {"name": "other-rules", "enforcement": "active"}, owner="otherorg"
    )
    assert "other-rules" in other_org.rulesets
    assert github_org.list_rulesets(owner="otherorg", fields="name") == ["other-rules"]
    assert github_org.list_rulesets(fields="name") == ["org-rules"]
    assert github_org.get_ruleset(created["id"], owner="otherorg")["name"] == "other-rules"
    github_org.update_ruleset(created["id"], {"enforcement": "disabled"}, owner="otherorg")
    assert other_org.get_ruleset(created["id"]).enforcement == "disabled"
    assert github_org.delete_ruleset(created["id"], owner="otherorg") is True
    assert "other-rules" not in other_org.rulesets


def test_list_teams_owner(github_org):
    assert set(github_org.list_teams(owner="otherorg")) == {"Team X"}
    assert set(github_org.list_teams()) == {"Team A"}


def test_get_team_owner(github_org):
    assert github_org.get_team("Team X", owner="otherorg")["slug"] == "team-x"


def test_add_team_repo_owner(github_org, fake_state):
    ret = github_org.add_team_repo("other-repo", "Team X", permission="push", owner="otherorg")
    assert ret is True
    team = fake_state.get_org("otherorg").get_team("team-x")
    assert team.repos[("otherorg", "other-repo")] == "push"
    repos = github_org.list_team_repos("Team X", owner="otherorg")
    assert repos["other-repo"]["permission"] == "push"


def test_team_owner_user_fails(github_org):
    # Users cannot own teams
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.list_teams(owner="user1")
