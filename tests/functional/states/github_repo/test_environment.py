CUSTOM_POLICY = {"protected_branches": False, "custom_branch_policies": True}
PROTECTED_POLICY = {"protected_branches": True, "custom_branch_policies": False}


def test_environment_present_create(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.environment_present(name="staging", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "environment" in ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    assert ("staging" in fake_org.get_repo("repo-a").environments) is not testmode


def test_environment_present_create_with_branches(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.environment_present(
        name="staging", deployment_branches=["main", "staging/*"], test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "environment" in ret.changes
    assert ret.changes["deployment_branches"]["new"] == ["main", "staging/*"]
    assert (len(fake_github.mutations()) == before) is testmode
    if testmode:
        assert "staging" not in fake_org.get_repo("repo-a").environments
    else:
        env = fake_org.get_repo("repo-a").get_environment("staging")
        assert env.deployment_branch_policy == CUSTOM_POLICY
        assert {policy.name for policy in env.branch_policies} == {"main", "staging/*"}
        rerun = github_repo.environment_present(
            name="staging", deployment_branches=["main", "staging/*"]
        )
        assert rerun.result is True
        assert not rerun.changes


def test_environment_present_idempotent(github_repo, fake_github, testmode):
    ret = github_repo.environment_present(
        name="release", deployment_branches=["main"], test=testmode
    )
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_environment_present_branch_pattern_drift(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.environment_present(
        name="release", deployment_branches=["main", "hotfix/*"], test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"deployment_branches": {"old": ["main"], "new": ["hotfix/*", "main"]}}
    assert (len(fake_github.mutations()) == before) is testmode
    env = fake_org.get_repo("repo-a").get_environment("release")
    expected = {"main"} if testmode else {"main", "hotfix/*"}
    assert {policy.name for policy in env.branch_policies} == expected


def test_environment_present_removes_stale_patterns(github_repo, fake_org, testmode):
    ret = github_repo.environment_present(
        name="release", deployment_branches=["develop"], test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "deployment_branches" in ret.changes
    env = fake_org.get_repo("repo-a").get_environment("release")
    expected = {"main"} if testmode else {"develop"}
    assert {policy.name for policy in env.branch_policies} == expected


def test_environment_present_wait_timer_drift_keeps_policy(
    github_repo, fake_github, fake_org, testmode
):
    before = len(fake_github.mutations())
    ret = github_repo.environment_present(name="release", wait_timer=30, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"wait_timer": {"old": 0, "new": 30}}
    assert (len(fake_github.mutations()) == before) is testmode
    env = fake_org.get_repo("repo-a").get_environment("release")
    if not testmode:
        assert env.wait_timer == 30
    # The unmanaged branch policy is carried over, not reset
    assert env.deployment_branch_policy == CUSTOM_POLICY
    assert {policy.name for policy in env.branch_policies} == {"main"}


def test_environment_present_protected_branches(github_repo, fake_org, testmode):
    ret = github_repo.environment_present(
        name="release", deployment_branches="protected", test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["deployment_branch_policy"]["new"] == PROTECTED_POLICY
    env = fake_org.get_repo("repo-a").get_environment("release")
    expected = CUSTOM_POLICY if testmode else PROTECTED_POLICY
    assert env.deployment_branch_policy == expected


def test_environment_present_all_branches(github_repo, fake_org, testmode):
    ret = github_repo.environment_present(name="release", deployment_branches="all", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["deployment_branch_policy"]["new"] is None
    env = fake_org.get_repo("repo-a").get_environment("release")
    expected = CUSTOM_POLICY if testmode else None
    assert env.deployment_branch_policy == expected


def test_environment_present_reviewers(github_repo, fake_org, testmode):
    reviewers = [{"type": "User", "id": 42}]
    ret = github_repo.environment_present(name="release", reviewers=reviewers, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["reviewers"]["new"] == reviewers
    if not testmode:
        assert fake_org.get_repo("repo-a").get_environment("release").reviewers == reviewers
        rerun = github_repo.environment_present(name="release", reviewers=reviewers)
        assert rerun.result is True
        assert not rerun.changes


def test_environment_present_invalid_branches(github_repo, fake_github):
    ret = github_repo.environment_present(name="release", deployment_branches=42)
    assert ret.result is False
    assert "deployment_branches" in ret.comment
    assert not fake_github.mutations()


def test_environment_absent(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.environment_absent(name="release", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    assert ("release" in fake_org.get_repo("repo-a").environments) is testmode
    if not testmode:
        rerun = github_repo.environment_absent(name="release")
        assert rerun.result is True
        assert not rerun.changes


def test_environment_absent_already(github_repo, fake_github, testmode):
    ret = github_repo.environment_absent(name="ghost", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()
