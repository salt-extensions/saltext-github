def test_actions_secret_present_create(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.actions_secret_present(name="NEW_SECRET", value="s3cr3t", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    # The value must never leak into the state output
    assert "s3cr3t" not in str(ret.changes) + ret.comment
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    if testmode:
        assert "NEW_SECRET" not in repo.secrets
    else:
        assert repo.get_secret("NEW_SECRET").value == "s3cr3t"
        rerun = github.actions_secret_present(name="NEW_SECRET", value="s3cr3t")
        assert rerun.result is True
        assert not rerun.changes


def test_actions_secret_present_existing_untouched(github, fake_github, fake_org, testmode):
    # Secret values are write-only, so an existing secret counts as present
    ret = github.actions_secret_present(name="existing_secret", value="other", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert "write-only" in ret.comment
    assert not fake_github.mutations()
    assert fake_org.get_repo("repo-a").get_secret("EXISTING_SECRET").value == "hunter2"


def test_actions_secret_present_force(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.actions_secret_present(
        name="EXISTING_SECRET", value="rotated", force=True, test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert "rotated" not in str(ret.changes) + ret.comment
    assert (len(fake_github.mutations()) == before) is testmode
    expected = "hunter2" if testmode else "rotated"
    assert fake_org.get_repo("repo-a").get_secret("EXISTING_SECRET").value == expected


def test_actions_secret_present_requires_value(github, fake_github):
    ret = github.actions_secret_present(name="ANOTHER_SECRET")
    assert ret.result is False
    assert "value is required" in ret.comment
    assert not fake_github.mutations()


def test_actions_secret_present_missing_repo(github):
    ret = github.actions_secret_present(name="NEW_SECRET", value="s3cr3t", repo_name="ghost")
    assert ret.result is False
    assert "Failed to list Actions secrets" in ret.comment


def test_actions_secret_absent(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.actions_secret_absent(name="existing_secret", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    assert ("EXISTING_SECRET" in fake_org.get_repo("repo-a").secrets) is testmode
    if not testmode:
        rerun = github.actions_secret_absent(name="existing_secret")
        assert rerun.result is True
        assert not rerun.changes


def test_actions_secret_absent_already(github, fake_github, testmode):
    ret = github.actions_secret_absent(name="GHOST", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()
