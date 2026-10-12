def test_get_workflow_permissions(github):
    ret = github.get_workflow_permissions()
    assert ret == {
        "default_workflow_permissions": "write",
        "can_approve_pull_request_reviews": False,
    }


def test_set_workflow_permissions(github, fake_org):
    assert (
        github.set_workflow_permissions(
            default_workflow_permissions="read", can_approve_pull_request_reviews=True
        )
        is True
    )
    repo = fake_org.get_repo("repo-a")
    assert repo.data.default_workflow_permissions == "read"
    assert repo.data.can_approve_pull_request_reviews is True


def test_set_workflow_permissions_partial(github, fake_org):
    assert github.set_workflow_permissions(can_approve_pull_request_reviews=True) is True
    repo = fake_org.get_repo("repo-a")
    # The other setting is left untouched
    assert repo.data.default_workflow_permissions == "write"
    assert repo.data.can_approve_pull_request_reviews is True
