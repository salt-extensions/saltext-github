def test_secrets_roundtrip(res_modules, for_resource, fake_org):
    repo = fake_org.get_repo("repo-a")
    with for_resource("testorg/repo-a"):
        assert list(res_modules["actions.list_secrets"]()) == ["EXISTING_SECRET"]

        assert res_modules["actions.set_secret"]("NEW_SECRET", "hunter3") is True
        # The fake decrypts the submitted sealed box end-to-end
        assert repo.get_secret("NEW_SECRET").value == "hunter3"

        assert res_modules["actions.get_secret"]("NEW_SECRET")["name"] == "NEW_SECRET"

        assert res_modules["actions.remove_secret"]("NEW_SECRET") is True
        assert "NEW_SECRET" not in repo.secrets


def test_workflow_permissions(res_modules, for_resource, fake_org):
    with for_resource("testorg/repo-a"):
        current = res_modules["actions.get_workflow_permissions"]()
        assert current == {
            "default_workflow_permissions": "write",
            "can_approve_pull_request_reviews": False,
        }
        assert (
            res_modules["actions.set_workflow_permissions"](
                default_workflow_permissions="read", can_approve_pull_request_reviews=True
            )
            is True
        )
    repo = fake_org.get_repo("repo-a")
    assert repo.default_workflow_permissions == "read"
    assert repo.can_approve_pull_request_reviews is True
