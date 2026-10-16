"""
Repository operations with tokens that are not tied to a user account
(e.g. GitHub App installation tokens). The functional fake API always
models a user token, so these paths are unit-only.
"""

from unittest.mock import MagicMock
from unittest.mock import patch

import github as pygithub
import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import client as gh_client
from saltext.github.utils.gh import repos as gh_repos


@pytest.fixture
def user_account():
    account = MagicMock()
    account.type = "User"
    account.login = "someuser"
    return account


@pytest.fixture
def conn(user_account):
    """
    A connection whose token cannot resolve ``GET /user``, knowing a
    single user-type account ``someuser``.
    """

    def get_user(login=None):
        if login is None:
            raise pygithub.GithubException(
                403, {"message": "Resource not accessible by integration"}, None
            )
        assert login == user_account.login
        return user_account

    with patch("saltext.github.utils.gh.client.github.Github", autospec=True):
        connection = gh_client.GitHubConnection("token")
    connection.client.get_user.side_effect = get_user
    return connection


def test_list_all_user_owner_falls_back_to_public_listing(conn, user_account):
    repo = MagicMock()
    repo.name = "repo-a"
    user_account.get_repos.return_value = [repo]

    assert gh_repos.list_all(conn, owner="someuser") == [repo]
    # The private-repos-included /user/repos listing is unavailable,
    # /users/{owner}/repos takes no affiliation parameter
    user_account.get_repos.assert_called_once_with()


def test_create_user_owner_raises_intended_error(conn):
    with pytest.raises(CommandExecutionError, match="Cannot create a repository for 'someuser'"):
        gh_repos.create(conn, "new-repo", owner="someuser")
