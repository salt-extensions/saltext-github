from saltext.github.utils import github

def test_get_user_pubkeys():
    # should fail, becausse we only want to allow a list
    users = {}
    assert(github.get_user_pubkeys(users) == {"Error": "A list of users is expected"})
