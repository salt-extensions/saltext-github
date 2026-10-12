def test_workflow_permissions_managed(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.workflow_permissions_managed(
        name="repo-a",
        default_workflow_permissions="read",
        can_approve_pull_request_reviews=True,
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["old"] == {
        "default_workflow_permissions": "write",
        "can_approve_pull_request_reviews": False,
    }
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    if testmode:
        assert repo.data.default_workflow_permissions == "write"
        assert repo.data.can_approve_pull_request_reviews is False
    else:
        assert repo.data.default_workflow_permissions == "read"
        assert repo.data.can_approve_pull_request_reviews is True
        rerun = github.workflow_permissions_managed(
            name="repo-a",
            default_workflow_permissions="read",
            can_approve_pull_request_reviews=True,
        )
        assert rerun.result is True
        assert not rerun.changes


def test_workflow_permissions_managed_unspecified_setting_untouched(github, fake_org, testmode):
    ret = github.workflow_permissions_managed(
        name="repo-a", default_workflow_permissions="read", test=testmode
    )
    assert ret.result is not False
    assert list(ret.changes["new"]) == ["default_workflow_permissions"]
    repo = fake_org.get_repo("repo-a")
    assert repo.data.can_approve_pull_request_reviews is False


def test_workflow_permissions_managed_idempotent(github, fake_github, testmode):
    ret = github.workflow_permissions_managed(
        name="repo-a", can_approve_pull_request_reviews=False, test=testmode
    )
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_workflow_permissions_managed_repo_name_override(github, fake_org, testmode):
    ret = github.workflow_permissions_managed(
        name="restrict Actions",
        repo_name="repo-b",
        default_workflow_permissions="read",
        test=testmode,
    )
    assert ret.result is not False
    expected = "write" if testmode else "read"
    assert fake_org.get_repo("repo-b").data.default_workflow_permissions == expected


def test_workflow_permissions_managed_no_settings(github):
    ret = github.workflow_permissions_managed(name="repo-a")
    assert ret.result is False
    assert "At least one setting" in ret.comment


def test_workflow_permissions_managed_missing_repo(github):
    ret = github.workflow_permissions_managed(name="ghost", default_workflow_permissions="read")
    assert ret.result is False
    assert "Failed to get workflow permissions" in ret.comment
