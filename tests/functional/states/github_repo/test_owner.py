"""
Verify that the ``github_repo`` states can manage repositories of other
owners (incl. user-owned ones) via the ``owner`` argument.
"""


def test_present_update_user_owned(github_repo, fake_github, fake_user, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.present("user-repo", owner="user1", description="Managed", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {
        "old": {"description": "Test repo user-repo"},
        "new": {"description": "Managed"},
    }
    assert (len(fake_github.mutations()) == before) is testmode
    expected = "Test repo user-repo" if testmode else "Managed"
    assert fake_user.get_repo("user-repo").description == expected


def test_present_create_auth_user(github_repo, fake_github, fake_user, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.present("brand-new", owner="user1", description="Mine", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"created": "brand-new"}
    assert (len(fake_github.mutations()) == before) is testmode
    assert ("brand-new" in fake_user.repos) is not testmode


def test_present_create_foreign_user_fails(github_repo, fake_state):
    # Repos can only be created for orgs and the authenticated user.
    # This is only detected on application since it requires owner
    # resolution, which the projection does not perform.
    ret = github_repo.present("brand-new", owner="user2")
    assert ret.result is False
    assert "only supports creating" in ret.comment
    assert not ret.changes
    assert "brand-new" not in fake_state.get_user("user2").repos


def test_present_teams_foreign_org(github_repo, fake_state, testmode):
    # Teams of the repo's owning org can be managed on its repos
    ret = github_repo.present(
        "other-repo", owner="otherorg", teams={"Team X": "push"}, test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"teams_added": ["Team X"]}
    team = fake_state.get_org("otherorg").get_team("team-x")
    assert (("otherorg", "other-repo") in team.repos) is not testmode


def test_present_teams_user_owner_fails(github_repo):
    # Users do not own teams, so the team resolution in the owning
    # "org" fails. Like for nonexistent teams, this only surfaces on
    # application since the diff does not resolve missing teams.
    ret = github_repo.present("user-repo", owner="user1", teams={"Team A": "push"})
    assert ret.result is False
    assert "Not Found" in ret.comment
    assert not ret.changes


def test_present_explicit_profile_owner_manages_teams(github_repo, fake_org, testmode):
    # An explicit owner equal to the profile's owner keeps teams usable
    ret = github_repo.present("repo-b", owner="testorg", teams={"Team A": "push"}, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"teams_added": ["Team A"]}
    team = fake_org.get_team("team-a")
    assert (("testorg", "repo-b") in team.repos) is not testmode


def test_absent_user_owned(github_repo, fake_github, fake_user, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.absent("user-repo", owner="user1", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"deleted": "user-repo"}
    assert (len(fake_github.mutations()) == before) is testmode
    assert ("user-repo" in fake_user.repos) is testmode


def test_label_present_user_owned(github_repo, fake_user, testmode):
    ret = github_repo.label_present(
        name="release", color="00ff00", repo_name="user-repo", owner="user1", test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"created": "release"}
    assert ("release" in fake_user.get_repo("user-repo").labels) is not testmode
