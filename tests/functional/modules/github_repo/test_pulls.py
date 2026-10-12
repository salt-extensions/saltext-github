def test_list_pulls(github_repo):
    ret = github_repo.list_pulls()
    assert [pr_["title"] for pr_ in ret] == ["Fix the bug"]
    assert ret[0]["user"]["login"] == "user2"
    assert ret[0]["base"]["ref"] == "main"
    assert ret[0]["head"]["ref"] == "bugfix"
