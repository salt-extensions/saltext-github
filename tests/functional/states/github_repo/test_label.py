def test_label_present_create(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.label_present(
        name="release", color="#00FF00", description="Release automation", test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["old"] is None
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    if testmode:
        assert "release" not in repo.labels
    else:
        label = repo.get_label("release")
        assert label.color == "00ff00"
        assert label.description == "Release automation"
        rerun = github_repo.label_present(
            name="release", color="#00FF00", description="Release automation"
        )
        assert rerun.result is True
        assert not rerun.changes


def test_label_present_idempotent(github_repo, fake_github, testmode):
    # Color comparison ignores case and a leading #
    ret = github_repo.label_present(
        name="bug", color="#D73A4A", description="Something is broken", test=testmode
    )
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_label_present_unmanaged_settings(github_repo, fake_github, testmode):
    ret = github_repo.label_present(name="bug", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_label_present_color_drift(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.label_present(name="bug", color="ff0000", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"old": {"color": "d73a4a"}, "new": {"color": "ff0000"}}
    assert (len(fake_github.mutations()) == before) is testmode
    label = fake_org.get_repo("repo-a").get_label("bug")
    expected = "d73a4a" if testmode else "ff0000"
    assert label.color == expected
    # Unmanaged settings are left untouched
    assert label.description == "Something is broken"


def test_label_present_description_drift(github_repo, fake_org, testmode):
    ret = github_repo.label_present(name="bug", description="Defect", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["new"] == {"description": "Defect"}
    label = fake_org.get_repo("repo-a").get_label("bug")
    expected = "Something is broken" if testmode else "Defect"
    assert label.description == expected


def test_label_present_missing_repo(github_repo):
    # A missing repo is indistinguishable from a missing label (404),
    # so the failure surfaces during the creation attempt
    ret = github_repo.label_present(name="bug", repo_name="ghost")
    assert ret.result is False
    assert "Failed to create label" in ret.comment


def test_label_absent(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.label_absent(name="bug", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    assert ("bug" in fake_org.get_repo("repo-a").labels) is testmode
    if not testmode:
        rerun = github_repo.label_absent(name="bug")
        assert rerun.result is True
        assert not rerun.changes


def test_label_absent_already(github_repo, fake_github, testmode):
    ret = github_repo.label_absent(name="ghost", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()
