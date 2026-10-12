def test_ruleset_present_idempotent(github_org, fake_github, testmode):
    ret = github_org.ruleset_present(
        name="org-rules",
        ruleset_params={"target": "branch", "enforcement": "active"},
        test=testmode,
    )
    assert ret.result is True
    assert not ret.changes
    assert "already configured" in ret.comment
    assert not fake_github.mutations()


def test_ruleset_present_ignores_server_populated_fields(github_org, testmode):
    # id/created_at/source etc. in the server response must not register
    # as drift when only managed params are compared
    ret = github_org.ruleset_present(
        name="org-rules", ruleset_params={"enforcement": "active"}, test=testmode
    )
    assert ret.result is True
    assert not ret.changes


def test_ruleset_present_converges_drift(github_org, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_org.ruleset_present(
        name="org-rules",
        ruleset_params={"target": "branch", "enforcement": "evaluate"},
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["old"] == {"enforcement": "active"}
    assert ret.changes["new"] == {"enforcement": "evaluate"}
    assert (len(fake_github.mutations()) == before) is testmode
    expected = "active" if testmode else "evaluate"
    assert fake_org.rulesets["org-rules"].enforcement == expected
    if not testmode:
        rerun = github_org.ruleset_present(
            name="org-rules", ruleset_params={"target": "branch", "enforcement": "evaluate"}
        )
        assert rerun.result is True
        assert not rerun.changes


def test_ruleset_present_create(github_org, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_org.ruleset_present(
        name="new-rules",
        ruleset_params={"target": "branch", "enforcement": "active"},
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["old"] is None
    assert (len(fake_github.mutations()) == before) is testmode
    assert ("new-rules" in fake_org.rulesets) is not testmode


def test_ruleset_present_create_failure(github_org):
    ret = github_org.ruleset_present(
        name="fresh-rules", ruleset_params={"enforcement": "active", "bogus_param": True}
    )
    assert ret.result is False
    assert "Failed to create ruleset" in ret.comment
    assert not ret.changes


def test_ruleset_present_update_failure(github_org):
    # Parameters unknown to the API are rejected with a validation error
    ret = github_org.ruleset_present(
        name="org-rules", ruleset_params={"enforcement": "evaluate", "bogus_param": True}
    )
    assert ret.result is False
    assert "Failed to update ruleset" in ret.comment
    assert not ret.changes


def test_ruleset_absent(github_org, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_org.ruleset_absent(name="org-rules", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert bool(list(fake_org.rulesets)) is testmode
    assert ret.changes == {"old": "Ruleset org-rules exists", "new": "Ruleset org-rules deleted"}
    if testmode:
        assert "would have been deleted" in ret.comment
    else:
        rerun = github_org.ruleset_absent(name="org-rules")
        assert rerun.result is True
        assert not rerun.changes


def test_ruleset_absent_missing(github_org, fake_github, testmode):
    ret = github_org.ruleset_absent(name="ghost-rules", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()
