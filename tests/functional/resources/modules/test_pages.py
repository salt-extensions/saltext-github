import pytest

from saltext.github.utils.gh.exceptions import GitHubNotFoundError


def test_setup_get_update_remove(res_modules, for_resource, fake_org):
    repo = fake_org.get_repo("repo-a")
    with for_resource("testorg/repo-a"):
        with pytest.raises(GitHubNotFoundError):
            res_modules["pages.get"]()

        res_modules["pages.setup"](build_type="workflow")
        assert res_modules["pages.get"]()["build_type"] == "workflow"
        assert repo.pages.build_type == "workflow"

        assert res_modules["pages.update"](https_enforced=True) is True
        assert repo.pages.https_enforced is True

        assert res_modules["pages.remove"]() is True
        with pytest.raises(GitHubNotFoundError):
            res_modules["pages.get"]()
