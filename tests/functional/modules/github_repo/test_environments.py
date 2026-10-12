import pytest
from salt.exceptions import CommandExecutionError

CUSTOM_POLICY = {"protected_branches": False, "custom_branch_policies": True}


def test_list_environments(github_repo):
    ret = github_repo.list_environments()
    assert [env["name"] for env in ret] == ["release"]


def test_get_environment(github_repo):
    ret = github_repo.get_environment("release")
    assert ret["name"] == "release"
    assert ret["deployment_branch_policy"] == CUSTOM_POLICY


def test_get_environment_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.get_environment("ghost")


def test_set_environment_create(github_repo, fake_org):
    ret = github_repo.set_environment("staging", wait_timer=5)
    assert ret["name"] == "staging"
    env = fake_org.get_repo("repo-a").get_environment("staging")
    assert env.wait_timer == 5
    assert env.deployment_branch_policy is None


def test_set_environment_carries_over_policy(github_repo, fake_org):
    # A PUT replaces the whole config, the wrapper is expected to carry
    # over the current branch policy when it is not specified.
    github_repo.set_environment("release", wait_timer=10)
    env = fake_org.get_repo("repo-a").get_environment("release")
    assert env.wait_timer == 10
    assert env.deployment_branch_policy == CUSTOM_POLICY


def test_set_environment_reset_policy(github_repo, fake_org):
    github_repo.set_environment("release", deployment_branch_policy=None)
    env = fake_org.get_repo("repo-a").get_environment("release")
    assert env.deployment_branch_policy is None


def test_set_environment_reviewers(github_repo, fake_org):
    github_repo.set_environment("release", reviewers=[{"type": "User", "id": 42}])
    env = fake_org.get_repo("repo-a").get_environment("release")
    assert env.reviewers == [{"type": "User", "id": 42}]


def test_remove_environment(github_repo, fake_org):
    assert github_repo.remove_environment("release") is True
    assert "release" not in fake_org.get_repo("repo-a").environments


def test_remove_environment_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.remove_environment("ghost")


def test_list_deployment_branch_policies(github_repo):
    ret = github_repo.list_deployment_branch_policies("release")
    assert [policy["name"] for policy in ret] == ["main"]


def test_add_deployment_branch_policy(github_repo, fake_org):
    ret = github_repo.add_deployment_branch_policy("release", "release/*")
    assert ret["name"] == "release/*"
    env = fake_org.get_repo("repo-a").get_environment("release")
    assert {policy.name for policy in env.branch_policies} == {"main", "release/*"}


def test_remove_deployment_branch_policy(github_repo, fake_org):
    existing = next(iter(fake_org.get_repo("repo-a").get_environment("release").branch_policies))
    assert github_repo.remove_deployment_branch_policy("release", existing.id) is True
    assert len(fake_org.get_repo("repo-a").get_environment("release").branch_policies) == 0
