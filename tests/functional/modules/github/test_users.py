def test_list_users(github):
    assert sorted(github.list_users()) == ["user1", "user2"]


def test_get_user_member_shortcut(github):
    assert github.get_user("user1") is True


def test_get_user_details_member(github):
    ret = github.get_user("user1", user_details=True)
    assert ret["login"] == "user1"
    assert ret["company"] == "Example Corp"
    assert ret["in_org"] is True
    assert ret["membership_state"] == "active"


def test_get_user_details_nonmember(github):
    ret = github.get_user("newuser", user_details=True)
    assert ret["in_org"] is False
    assert ret["membership_state"] == "nonexistent"


def test_get_user_unknown(github):
    assert github.get_user("ghost", user_details=True) is False


def test_add_user(github, fake_org):
    assert github.add_user("newuser") is True
    assert fake_org.get_member("newuser").state == "pending"
    ret = github.get_user("newuser", user_details=True)
    assert ret["membership_state"] == "pending"
    assert ret["in_org"] is False


def test_remove_user(github, fake_org):
    assert github.remove_user("user2") is True
    assert "user2" not in [member.data.login for member in fake_org.members]
    assert sorted(github.list_users(ignore_cache=True)) == ["user1"]


def test_remove_user_not_a_member(github):
    # Idempotent: the user is not a member afterwards
    assert github.remove_user("newuser") is True


def test_remove_user_unknown(github):
    assert github.remove_user("ghost") is False
