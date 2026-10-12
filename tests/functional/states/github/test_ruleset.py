import pytest


@pytest.fixture
def repo_ruleset_args():
    return {
        "ruleset_type": "repo",
        "owner": "testorg",
        "repo_name": "repo-a",
    }


def test_ruleset_present_idempotent(github, repo_ruleset_args, testmode):
    ret = github.ruleset_present(
        name="repo-rules",
        ruleset_params={"target": "branch", "enforcement": "disabled"},
        test=testmode,
        **repo_ruleset_args,
    )
    assert ret.result is True
    assert not ret.changes
    assert "present" in ret.comment


def test_ruleset_present_ignores_server_populated_fields(github, repo_ruleset_args, testmode):
    # id/created_at/source etc. in the server response must not register
    # as drift when only managed params are compared
    ret = github.ruleset_present(
        name="repo-rules",
        ruleset_params={"enforcement": "disabled"},
        test=testmode,
        **repo_ruleset_args,
    )
    assert ret.result is True
    assert not ret.changes


def test_ruleset_present_converges_drift(
    github, fake_github, fake_org, repo_ruleset_args, testmode
):
    before = len(fake_github.mutations())
    ret = github.ruleset_present(
        name="repo-rules",
        ruleset_params={"target": "branch", "enforcement": "active"},
        test=testmode,
        **repo_ruleset_args,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ("will be" in ret.comment) is testmode
    assert ret.changes["old"] == {"enforcement": "disabled"}
    assert ret.changes["new"] == {"enforcement": "active"}
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    expected = "disabled" if testmode else "active"
    assert repo.rulesets["repo-rules"].enforcement == expected
    if not testmode:
        rerun = github.ruleset_present(
            name="repo-rules",
            ruleset_params={"target": "branch", "enforcement": "active"},
            **repo_ruleset_args,
        )
        assert rerun.result is True
        assert not rerun.changes


def test_ruleset_present_create(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.ruleset_present(
        name="new-rules",
        ruleset_type="org",
        ruleset_params={"target": "branch", "enforcement": "active"},
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ("will be" in ret.comment) is testmode
    assert ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    assert ("new-rules" in fake_org.rulesets) is not testmode


def test_ruleset_absent(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.ruleset_absent(name="org-rules", ruleset_type="org", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert bool(list(fake_org.rulesets)) is testmode
    assert ret.changes == {"old": "ruleset org-rules exists", "new": "ruleset org-rules deleted"}
    if testmode:
        assert "will be deleted" in ret.comment
    else:
        rerun = github.ruleset_absent(name="org-rules", ruleset_type="org")
        assert rerun.result is True
        assert not rerun.changes


def test_ruleset_absent_missing(github, testmode):
    ret = github.ruleset_absent(name="ghost-rules", ruleset_type="org", test=testmode)
    assert ret.result is True
    assert not ret.changes


def test_ruleset_present_invalid_type(github):
    ret = github.ruleset_present(
        name="x", ruleset_type="bogus", ruleset_params={"enforcement": "active"}
    )
    assert ret.result is False
    assert "ruleset_type" in ret.comment


def test_ruleset_absent_invalid_type(github):
    ret = github.ruleset_absent(name="x", ruleset_type="bogus")
    assert ret.result is False
    assert "ruleset_type" in ret.comment


def test_ruleset_present_list_error(github):
    ret = github.ruleset_present(
        name="x",
        ruleset_type="repo",
        owner="testorg",
        repo_name="ghost",
        ruleset_params={"enforcement": "active"},
    )
    assert ret.result is False
    assert "error listing rulesets" in ret.comment


def test_ruleset_absent_list_error(github):
    ret = github.ruleset_absent(name="x", ruleset_type="repo", owner="testorg", repo_name="ghost")
    assert ret.result is False
    assert "error listing rulesets" in ret.comment


def test_ruleset_present_update_failure(github, repo_ruleset_args):
    # Parameters unknown to the API are rejected with a validation error
    ret = github.ruleset_present(
        name="repo-rules",
        ruleset_params={"enforcement": "disabled", "bogus_param": True},
        **repo_ruleset_args,
    )
    assert ret.result is False
    assert "Could not update ruleset" in ret.comment
    assert not ret.changes


def test_ruleset_present_create_failure(github):
    ret = github.ruleset_present(
        name="fresh-rules",
        ruleset_type="org",
        ruleset_params={"enforcement": "active", "bogus_param": True},
    )
    assert ret.result is False
    assert "could not be added" in ret.comment
    assert not ret.changes
