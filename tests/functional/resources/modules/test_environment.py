def test_list_get(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        environments = res_modules["environment.list"]()
        assert list(environments) == ["release"]
        assert res_modules["environment.get"]("release")["name"] == "release"


def test_set_remove(res_modules, for_resource, fake_org):
    repo = fake_org.get_repo("repo-a")
    with for_resource("testorg/repo-a"):
        res_modules["environment.set"]("staging", wait_timer=5)
        assert "staging" in repo.environments

        assert res_modules["environment.remove"]("staging") is True
        assert "staging" not in repo.environments


def test_branch_policies(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        policies = res_modules["environment.list_branch_policies"]("release")
        assert [policy["name"] for policy in policies] == ["main"]

        created = res_modules["environment.add_branch_policy"]("release", "release/*")
        policies = res_modules["environment.list_branch_policies"]("release", fields="name")
        assert sorted(policies) == ["main", "release/*"]

        assert res_modules["environment.remove_branch_policy"]("release", created["id"]) is True
        assert res_modules["environment.list_branch_policies"]("release", fields="name") == ["main"]
