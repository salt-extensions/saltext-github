def test_ruleset_present_idempotent(github_repo, fake_github, testmode):
    ret = github_repo.ruleset_present(
        name="repo-rules",
        ruleset_params={"target": "branch", "enforcement": "disabled"},
        test=testmode,
    )
    assert ret.result is True
    assert not ret.changes
    assert "already configured" in ret.comment
    assert not fake_github.mutations()


def test_ruleset_present_ignores_server_populated_fields(github_repo, testmode):
    # id/created_at/source etc. in the server response must not register
    # as drift when only managed params are compared
    ret = github_repo.ruleset_present(
        name="repo-rules", ruleset_params={"enforcement": "disabled"}, test=testmode
    )
    assert ret.result is True
    assert not ret.changes


def test_ruleset_present_converges_drift(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.ruleset_present(
        name="repo-rules",
        ruleset_params={"target": "branch", "enforcement": "active"},
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["old"] == {"enforcement": "disabled"}
    assert ret.changes["new"] == {"enforcement": "active"}
    assert (len(fake_github.mutations()) == before) is testmode
    expected = "disabled" if testmode else "active"
    assert fake_org.get_repo("repo-a").rulesets["repo-rules"].enforcement == expected
    if not testmode:
        rerun = github_repo.ruleset_present(
            name="repo-rules", ruleset_params={"target": "branch", "enforcement": "active"}
        )
        assert rerun.result is True
        assert not rerun.changes


def test_ruleset_present_create(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.ruleset_present(
        name="new-rules",
        repo_name="repo-b",
        ruleset_params={"target": "branch", "enforcement": "active"},
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"created": "new-rules"}
    assert (len(fake_github.mutations()) == before) is testmode
    assert ("new-rules" in fake_org.get_repo("repo-b").rulesets) is not testmode


def test_ruleset_present_list_error(github_repo):
    ret = github_repo.ruleset_present(
        name="x", repo_name="ghost", ruleset_params={"enforcement": "active"}
    )
    assert ret.result is False
    assert "Not Found" in ret.comment


def test_ruleset_present_update_failure(github_repo):
    # Parameters unknown to the API are rejected with a validation error
    ret = github_repo.ruleset_present(
        name="repo-rules", ruleset_params={"enforcement": "active", "bogus_param": True}
    )
    assert ret.result is False
    assert "422" in ret.comment
    assert not ret.changes


def test_ruleset_absent(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.ruleset_absent(name="repo-rules", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert bool(list(fake_org.get_repo("repo-a").rulesets)) is testmode
    assert ret.changes == {"deleted": "repo-rules"}
    if not testmode:
        rerun = github_repo.ruleset_absent(name="repo-rules")
        assert rerun.result is True
        assert not rerun.changes


def test_ruleset_absent_missing(github_repo, fake_github, testmode):
    ret = github_repo.ruleset_absent(name="ghost-rules", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_ruleset_absent_list_error(github_repo):
    ret = github_repo.ruleset_absent(name="x", repo_name="ghost")
    assert ret.result is False
    assert "Not Found" in ret.comment
