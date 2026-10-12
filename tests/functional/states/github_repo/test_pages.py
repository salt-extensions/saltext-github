def test_pages_present_enable(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.pages_present(name="repo-a", build_type="workflow", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"created": "repo-a"}
    assert (len(fake_github.mutations()) == before) is testmode
    pages = fake_org.get_repo("repo-a").pages
    if testmode:
        assert pages is None
    else:
        assert pages.build_type == "workflow"
        rerun = github_repo.pages_present(name="repo-a", build_type="workflow")
        assert rerun.result is True
        assert not rerun.changes


def test_pages_present_enable_with_https(github_repo, fake_org, testmode):
    ret = github_repo.pages_present(
        name="repo-a", build_type="workflow", https_enforced=True, test=testmode
    )
    assert ret.result is not False
    if not testmode:
        assert fake_org.get_repo("repo-a").pages.https_enforced is True


def test_pages_present_idempotent(github_repo, fake_github, testmode):
    ret = github_repo.pages_present(
        name="repo-b", build_type="legacy", source_branch="gh-pages", source_path="/", test=testmode
    )
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_pages_present_build_type_drift(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.pages_present(name="repo-b", build_type="workflow", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {
        "old": {"build_type": "legacy"},
        "new": {"build_type": "workflow"},
    }
    assert (len(fake_github.mutations()) == before) is testmode
    expected = "legacy" if testmode else "workflow"
    assert fake_org.get_repo("repo-b").pages.build_type == expected


def test_pages_present_source_drift(github_repo, fake_org, testmode):
    ret = github_repo.pages_present(name="repo-b", source_branch="docs", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["new"] == {"source_branch": "docs"}
    expected = "gh-pages" if testmode else "docs"
    assert fake_org.get_repo("repo-b").pages.source["branch"] == expected


def test_pages_present_cname(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.pages_present(name="repo-b", cname="docs.example.com", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"old": {"cname": None}, "new": {"cname": "docs.example.com"}}
    assert (len(fake_github.mutations()) == before) is testmode
    expected = None if testmode else "docs.example.com"
    assert fake_org.get_repo("repo-b").pages.cname == expected


def test_pages_present_missing_repo(github_repo):
    # A missing repo is indistinguishable from a missing Pages site (404),
    # so the failure surfaces during the creation attempt
    ret = github_repo.pages_present(name="ghost")
    assert ret.result is False
    assert "Not Found" in ret.comment


def test_pages_absent(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.pages_absent(name="repo-b", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"deleted": "repo-b"}
    assert (len(fake_github.mutations()) == before) is testmode
    assert (fake_org.get_repo("repo-b").pages is not None) is testmode
    if not testmode:
        rerun = github_repo.pages_absent(name="repo-b")
        assert rerun.result is True
        assert not rerun.changes


def test_pages_absent_already(github_repo, fake_github, testmode):
    ret = github_repo.pages_absent(name="repo-a", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()
