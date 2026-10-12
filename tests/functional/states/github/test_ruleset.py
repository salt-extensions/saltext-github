import pytest


@pytest.fixture
def repo_ruleset_args():
    return {
        "ruleset_type": "repo",
        "owner": "testorg",
        "repo_name": "repo-a",
    }


def test_ruleset_present_idempotent(github, repo_ruleset_args):
    ret = github.ruleset_present(
        name="repo-rules",
        ruleset_params={"target": "branch", "enforcement": "disabled"},
        **repo_ruleset_args,
    )
    assert ret.result is True
    assert not ret.changes
    assert "present" in ret.comment


def test_ruleset_present_ignores_server_populated_fields(github, repo_ruleset_args):
    # id/created_at/source etc. in the server response must not register
    # as drift when only managed params are compared
    ret = github.ruleset_present(
        name="repo-rules",
        ruleset_params={"enforcement": "disabled"},
        **repo_ruleset_args,
    )
    assert ret.result is True
    assert not ret.changes


def test_ruleset_present_converges_drift(github, fake_org, repo_ruleset_args):
    ret = github.ruleset_present(
        name="repo-rules",
        ruleset_params={"target": "branch", "enforcement": "active"},
        **repo_ruleset_args,
    )
    assert ret.result is True
    assert ret.changes["old"] == {"enforcement": "disabled"}
    assert ret.changes["new"] == {"enforcement": "active"}
    repo = fake_org.get_repo("repo-a")
    assert repo.rulesets["repo-rules"].enforcement == "active"

    rerun = github.ruleset_present(
        name="repo-rules",
        ruleset_params={"target": "branch", "enforcement": "active"},
        **repo_ruleset_args,
    )
    assert rerun.result is True
    assert not rerun.changes


def test_ruleset_present_drift_test_mode(github, fake_github, fake_org, repo_ruleset_args):
    before = len(fake_github.mutations())
    ret = github.ruleset_present(
        name="repo-rules",
        ruleset_params={"enforcement": "active"},
        test=True,
        **repo_ruleset_args,
    )
    assert ret.result is None
    assert ret.changes["new"] == {"enforcement": "active"}
    assert len(fake_github.mutations()) == before
    repo = fake_org.get_repo("repo-a")
    assert repo.rulesets["repo-rules"].enforcement == "disabled"


def test_ruleset_present_create(github, fake_org):
    ret = github.ruleset_present(
        name="new-rules",
        ruleset_type="org",
        ruleset_params={"target": "branch", "enforcement": "active"},
    )
    assert ret.result is True
    assert ret.changes
    assert "new-rules" in fake_org.rulesets


def test_ruleset_present_create_test_mode(github, fake_github):
    before = len(fake_github.mutations())
    ret = github.ruleset_present(
        name="new-rules",
        ruleset_type="org",
        ruleset_params={"target": "branch", "enforcement": "active"},
        test=True,
    )
    assert ret.result is None
    assert ret.changes
    assert len(fake_github.mutations()) == before


def test_ruleset_absent(github, fake_org):
    ret = github.ruleset_absent(name="org-rules", ruleset_type="org")
    assert ret.result is True
    assert ret.changes
    assert not list(fake_org.rulesets)

    rerun = github.ruleset_absent(name="org-rules", ruleset_type="org")
    assert rerun.result is True
    assert not rerun.changes


def test_ruleset_absent_missing_in_test_mode(github):
    ret = github.ruleset_absent(name="ghost-rules", ruleset_type="org", test=True)
    assert ret.result is True
    assert not ret.changes


def test_ruleset_absent_test_mode(github, fake_github, fake_org):
    before = len(fake_github.mutations())
    ret = github.ruleset_absent(name="org-rules", ruleset_type="org", test=True)
    assert ret.result is None
    assert len(fake_github.mutations()) == before
    assert list(fake_org.rulesets)
