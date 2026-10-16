from unittest.mock import MagicMock
from unittest.mock import patch

import github as pygithub
import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import client as gh_client
from saltext.github.utils.gh.exceptions import GitHubApiError
from saltext.github.utils.gh.exceptions import GitHubNotFoundError


@pytest.fixture
def requester():
    return MagicMock()


@pytest.fixture
def conn(requester):
    with patch(
        "saltext.github.utils.gh.client.github.Github",
        autospec=True,
        return_value=MagicMock(requester=requester),
    ):
        yield gh_client.GitHubConnection("token")


def test_query_decodes_json_string_data(conn, requester):
    requester.requestJson.return_value = (200, {}, '{"written": true}')

    ret = conn.query("repos", method="POST", data='{"some": "payload"}')

    assert ret == {"written": True}
    requester.requestJson.assert_called_once_with(
        "POST", "/repos", parameters=None, headers=None, input={"some": "payload"}
    )


def test_query_merges_paginated_results(conn, requester):
    requester.requestJson.side_effect = (
        (200, {"Link": '<https://example.com/repos?page=2>; rel="next"'}, '[{"id": 1}]'),
        (200, {}, '[{"id": 2}]'),
    )

    ret = conn.query(["repos"])

    assert ret == [{"id": 1}, {"id": 2}]
    assert requester.requestJson.call_args.kwargs["parameters"] == {"page": "2"}


def test_query_github_exception(conn, requester):
    requester.requestJson.side_effect = pygithub.GithubException(502, {"message": "bad gateway"})

    with pytest.raises(GitHubApiError, match="bad gateway") as exc:
        conn.query("repos")

    assert exc.value.status == 502


def test_query_error_response(conn, requester):
    requester.requestJson.return_value = (404, {}, '{"message": "Not Found"}')

    with pytest.raises(GitHubNotFoundError, match="404 Not Found") as exc:
        conn.query("repos")

    assert exc.value.status == 404
    assert exc.value.data == {"message": "Not Found"}


def test_query_unexpected_exception(conn, requester):
    requester.requestJson.side_effect = OSError("connection refused")

    with pytest.raises(CommandExecutionError, match="connection refused"):
        conn.query("repos")


def test_api_request_translates_pygithub_exceptions():
    @gh_client.api_request
    def _not_found():
        raise pygithub.UnknownObjectException(404, {"message": "Not Found"})

    @gh_client.api_request
    def _server_error():
        raise pygithub.GithubException(502, {"message": "bad gateway"})

    with pytest.raises(GitHubNotFoundError, match="404 Not Found") as exc:
        _not_found()
    assert exc.value.status == 404

    with pytest.raises(GitHubApiError, match="502 bad gateway") as exc:
        _server_error()
    assert exc.value.status == 502


@pytest.fixture
def token_conn():
    with patch("saltext.github.utils.gh.client.github.Github", autospec=True):
        yield gh_client.GitHubConnection("token")


def test_owner_defaults_to_token_user(conn):
    conn.client.get_user.return_value.login = "tokenuser"
    assert conn.owner == "tokenuser"
    conn.client.get_user.assert_called_once_with()
    # The resolution result is cached
    assert conn.owner == "tokenuser"
    conn.client.get_user.assert_called_once_with()


def test_owner_lookup_failure_hints_at_profile_parameter(conn):
    # GitHub App installation tokens are not tied to a user account
    conn.client.get_user.side_effect = pygithub.GithubException(
        403, {"message": "Resource not accessible by integration"}, None
    )
    with pytest.raises(CommandExecutionError, match="require the 'owner' profile parameter"):
        conn.owner  # pylint: disable=pointless-statement


def test_is_auth_user_matches_case_insensitively(conn):
    conn.client.get_user.return_value.login = "TokenUser"
    assert conn.is_auth_user("tokenuser") is True
    assert conn.is_auth_user("otheruser") is False


def test_is_auth_user_false_for_non_user_tokens(conn):
    # GitHub App installation tokens are not tied to a user account
    conn.client.get_user.side_effect = pygithub.GithubException(
        403, {"message": "Resource not accessible by integration"}, None
    )
    assert conn.is_auth_user("someuser") is False


def test_explicit_owner_skips_token_lookup():
    with patch("saltext.github.utils.gh.client.github.Github", autospec=True):
        explicit = gh_client.GitHubConnection("token", "testorg")
    assert explicit.owner == "testorg"
    explicit.client.get_user.assert_not_called()


def test_get_app_connection_ident_owner_case_insensitive():
    ident = gh_client.get_app_connection_ident(123, "TestOrg", "https://api.example.com")
    assert ident == gh_client.get_app_connection_ident(123, "testorg", "https://api.example.com")
    # Any other component changes the identity
    assert ident != gh_client.get_app_connection_ident(124, "testorg", "https://api.example.com")
    assert ident != gh_client.get_app_connection_ident(123, "otherorg", "https://api.example.com")
    assert ident != gh_client.get_app_connection_ident(123, "testorg", "https://api.example.org")
    assert ident != gh_client.get_connection_ident("token", "https://api.example.com")


def test_get_app_connection_ident_includes_permissions():
    def _ident(permissions=None):
        return gh_client.get_app_connection_ident(
            123, "testorg", "https://api.example.com", permissions
        )

    # Differently restricted profiles must not share connections/banks
    assert _ident({"contents": "read"}) != _ident()
    assert _ident({"contents": "read"}) != _ident({"contents": "write"})
    # Unset and empty are equivalent (both mean unrestricted), key order is irrelevant
    assert _ident({}) == _ident()
    assert _ident({"contents": "read", "issues": "write"}) == _ident(
        {"issues": "write", "contents": "read"}
    )


def test_connection_with_auth_instance_requires_ident():
    with pytest.raises(ValueError, match="requires 'ident'"):
        gh_client.GitHubConnection(pygithub.Auth.Token("token"))


def test_connection_with_auth_instance():
    auth = pygithub.Auth.Token("token")
    with patch("saltext.github.utils.gh.client.github.Github", autospec=True) as ghub:
        conn = gh_client.GitHubConnection(auth, "testorg", ident="abc123")
    assert conn.ident == "abc123"
    assert ghub.call_args.kwargs["auth"] is auth


def test_connection_explicit_ident_overrides_token_derivation():
    with patch("saltext.github.utils.gh.client.github.Github", autospec=True):
        conn = gh_client.GitHubConnection("token", ident="abc123")
    assert conn.ident == "abc123"


def test_build_app_auth_invalid_private_key():
    with pytest.raises(CommandExecutionError, match="Failed initializing GitHub App"):
        gh_client.build_app_auth(123, "not a private key", 42)


def test_build_app_auth(app_private_key):
    auth = gh_client.build_app_auth(123, app_private_key, "42")
    assert isinstance(auth, pygithub.Auth.AppInstallationAuth)
    assert auth.installation_id == 42
    assert auth.app_id == "123"
    assert auth.token_permissions is None


def test_build_app_auth_permissions(app_private_key):
    auth = gh_client.build_app_auth(123, app_private_key, 42, {"contents": "read"})
    assert auth.token_permissions == {"contents": "read"}


def test_revoke_installation_token(conn, requester):
    requester.auth = pygithub.Auth.AppAuth(123, "key").get_installation_auth(42)
    requester.requestJson.return_value = (204, {}, "")

    gh_client.revoke_installation_token(conn)

    requester.requestJson.assert_called_once_with(
        "DELETE", "/installation/token", parameters=None, headers=None, input=None
    )


def test_revoke_installation_token_requires_app_auth(conn, requester):
    requester.auth = pygithub.Auth.Token("token")
    with pytest.raises(CommandExecutionError, match="Only GitHub App"):
        gh_client.revoke_installation_token(conn)
    requester.requestJson.assert_not_called()


@pytest.fixture
def integration():
    with (
        patch("saltext.github.utils.gh.client._app_auth"),
        patch(
            "saltext.github.utils.gh.client.github.GithubIntegration", autospec=True
        ) as integration_cls,
    ):
        yield integration_cls.return_value


def _resolve():
    return gh_client.resolve_app_installation_id(123, "pem", "someowner", "https://example.com")


def test_resolve_app_installation_id_org(integration):
    integration.get_org_installation.return_value.id = 7
    assert _resolve() == 7
    integration.get_user_installation.assert_not_called()
    integration.close.assert_called_once_with()


def test_resolve_app_installation_id_user_fallback(integration):
    integration.get_org_installation.side_effect = pygithub.UnknownObjectException(
        404, {"message": "Not Found"}
    )
    integration.get_user_installation.return_value.id = 8
    assert _resolve() == 8


def test_resolve_app_installation_id_not_installed(integration):
    integration.get_org_installation.side_effect = pygithub.UnknownObjectException(
        404, {"message": "Not Found"}
    )
    integration.get_user_installation.side_effect = pygithub.UnknownObjectException(
        404, {"message": "Not Found"}
    )
    with pytest.raises(GitHubNotFoundError, match="does not appear to be installed"):
        _resolve()


def test_resolve_app_installation_id_api_error(integration):
    integration.get_org_installation.side_effect = pygithub.GithubException(
        502, {"message": "bad gateway"}
    )
    with pytest.raises(GitHubApiError, match="502 bad gateway"):
        _resolve()
