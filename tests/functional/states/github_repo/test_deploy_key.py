from tests.support.github import DEPLOY_KEY_A
from tests.support.github import DEPLOY_KEY_B


def test_deploy_key_present_create(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_present(name="autorelease", key=DEPLOY_KEY_B, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["old"] is None
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    added = [key for key in repo.deploy_keys if key.title == "autorelease"]
    assert bool(added) is not testmode
    if not testmode:
        assert added[0].key == DEPLOY_KEY_B


def test_deploy_key_present_idempotent(github_repo, fake_github, testmode):
    ret = github_repo.deploy_key_present(
        name="existing-key", key=DEPLOY_KEY_A, read_only=True, test=testmode
    )
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_deploy_key_present_ignores_key_comment(github_repo, fake_github, testmode):
    key = " ".join(DEPLOY_KEY_A.split()[:2]) + " another-comment"
    ret = github_repo.deploy_key_present(
        name="existing-key", key=key, read_only=True, test=testmode
    )
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_deploy_key_present_replaces_changed_key(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_present(
        name="existing-key", key=DEPLOY_KEY_B, read_only=True, test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["old"]["key"] == DEPLOY_KEY_A
    assert (len(fake_github.mutations()) == before) is testmode
    current = next(
        key for key in fake_org.get_repo("repo-a").deploy_keys if key.title == "existing-key"
    )
    expected = DEPLOY_KEY_A if testmode else DEPLOY_KEY_B
    assert current.key == expected
    if not testmode:
        rerun = github_repo.deploy_key_present(
            name="existing-key", key=DEPLOY_KEY_B, read_only=True
        )
        assert rerun.result is True
        assert not rerun.changes


def test_deploy_key_present_replaces_changed_read_only(
    github_repo, fake_github, fake_org, testmode
):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_present(name="existing-key", key=DEPLOY_KEY_A, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["new"]["read_only"] is False
    assert (len(fake_github.mutations()) == before) is testmode
    current = next(
        key for key in fake_org.get_repo("repo-a").deploy_keys if key.title == "existing-key"
    )
    assert current.read_only is testmode


def test_deploy_key_present_missing_repo(github_repo):
    ret = github_repo.deploy_key_present(name="autorelease", key=DEPLOY_KEY_B, repo_name="ghost")
    assert ret.result is False
    assert "Failed to list deploy keys" in ret.comment


def test_deploy_key_absent(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_absent(name="existing-key", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    assert bool(fake_org.get_repo("repo-a").deploy_keys) is testmode
    if not testmode:
        rerun = github_repo.deploy_key_absent(name="existing-key")
        assert rerun.result is True
        assert not rerun.changes


def test_deploy_key_absent_already(github_repo, fake_github, testmode):
    ret = github_repo.deploy_key_absent(name="ghost", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()
