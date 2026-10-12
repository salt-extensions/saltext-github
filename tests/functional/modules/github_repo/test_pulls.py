def test_list_pulls(github_repo):
    ret = github_repo.list_pulls()
    assert [pr_["title"] for pr_ in ret] == ["Fix the bug"]
    assert ret[0]["user"] == "user2"
    assert ret[0]["base_branch"] == "main"


def test_list_pulls_full_output(github_repo):
    ret = github_repo.list_pulls(output="full")
    assert ret[0]["head"]["ref"] == "bugfix"
