def test_get_milestones_min_output(github):
    ret = github.get_milestones(repo_name="repo-a")
    assert len(ret) == 2
    for milestone in ret.values():
        # min output strips these keys and must not crash when absent
        assert "creator" not in milestone
        assert "html_url" not in milestone
        assert "labels_url" not in milestone
    assert sorted(milestone["title"] for milestone in ret.values()) == ["v1.0", "v2.0"]


def test_get_milestones_full_output(github):
    ret = github.get_milestones(repo_name="repo-a", output="full")
    assert all(milestone["creator"]["login"] == "user1" for milestone in ret.values())


def test_get_milestone_by_number(github):
    ret = github.get_milestone(number=1, repo_name="repo-a")
    assert [milestone["title"] for milestone in ret.values()] == ["v1.0"]


def test_get_milestone_by_name(github):
    ret = github.get_milestone(name="v2.0", repo_name="repo-a")
    assert [milestone["title"] for milestone in ret.values()] == ["v2.0"]
