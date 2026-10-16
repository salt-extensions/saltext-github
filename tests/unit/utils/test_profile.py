"""
Tests for profile resolution into connections, particularly the
credential validation (token vs GitHub App auth).
"""

from unittest.mock import patch

import github as pygithub
import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh.client import get_app_connection_ident
from saltext.github.utils.gh.client import get_connection_ident

API_URL = "https://api.example.com"


def _opts(**profile):
    profile.setdefault("api_url", API_URL)
    profile.setdefault("cache", False)
    return {"github": profile}


def _get_conn(opts, context=None):
    return gh_profile.get_conn("github", opts=opts, context=context if context is not None else {})


def test_get_conn_rejects_token_and_app_id():
    with pytest.raises(CommandExecutionError, match="mutually exclusive"):
        _get_conn(_opts(token="hunter2", app_id=123, owner="testorg"))


def test_get_conn_requires_credentials():
    with pytest.raises(CommandExecutionError, match="missing authentication credentials"):
        _get_conn(_opts(owner="testorg"))


def test_get_conn_app_requires_owner():
    with pytest.raises(CommandExecutionError, match="requires the 'owner' parameter"):
        _get_conn(_opts(app_id=123, private_key="pem"))


@pytest.mark.parametrize(
    "extra",
    (
        {"private_key": "pem", "private_key_path": "/some/path"},
        {},
    ),
    ids=("both", "neither"),
)
def test_get_conn_app_requires_exactly_one_private_key(extra):
    with pytest.raises(CommandExecutionError, match="exactly one of 'private_key'"):
        _get_conn(_opts(app_id=123, owner="testorg", **extra))


def test_get_conn_app_private_key_path_read_error(tmp_path):
    with pytest.raises(CommandExecutionError, match="Failed reading 'private_key_path'"):
        _get_conn(
            _opts(app_id=123, owner="testorg", private_key_path=str(tmp_path / "missing.pem"))
        )


def test_get_conn_app_private_key_path(tmp_path, app_private_key):
    """
    App profiles with a key file and a pinned installation build a
    connection without any API request, deriving a token-independent
    identity.
    """
    key_file = tmp_path / "app.pem"
    key_file.write_text(app_private_key)
    conn = _get_conn(
        _opts(
            app_id=123,
            owner="testorg",
            private_key_path=str(key_file),
            installation_id=42,
        )
    )
    assert conn.ident == get_app_connection_ident(123, "testorg", API_URL)
    assert conn.owner == "testorg"


def test_get_conn_app_resolves_installation(app_private_key):
    with patch(
        "saltext.github.utils.gh.profile.resolve_app_installation_id", return_value=42
    ) as resolve:
        conn = _get_conn(_opts(app_id=123, owner="testorg", private_key=app_private_key))
    resolve.assert_called_once_with(123, app_private_key, "testorg", API_URL)
    auth = conn.client.requester.auth
    assert isinstance(auth, pygithub.Auth.AppInstallationAuth)
    assert auth.installation_id == 42


def test_get_conn_token_ident_unchanged():
    conn = _get_conn(_opts(token="hunter2", owner="testorg"))
    assert conn.ident == get_connection_ident("hunter2", API_URL)


def test_get_conn_token_rejects_permissions():
    with pytest.raises(CommandExecutionError, match="only valid for GitHub App"):
        _get_conn(_opts(token="hunter2", owner="testorg", permissions={"contents": "read"}))


def test_get_conn_app_permissions_must_be_a_mapping():
    with pytest.raises(CommandExecutionError, match="must be a mapping"):
        _get_conn(
            _opts(app_id=123, owner="testorg", private_key="pem", permissions="contents: read")
        )


def test_get_conn_app_permissions(app_private_key):
    """
    Restricted profiles pass the permissions through to the token mint
    and derive a distinct connection identity, so differently
    restricted profiles never share a connection.
    """
    permissions = {"contents": "read"}
    profile = _opts(
        app_id=123,
        owner="testorg",
        private_key=app_private_key,
        installation_id=42,
        permissions=permissions,
    )
    conn = _get_conn(profile)
    assert conn.client.requester.auth.token_permissions == permissions
    assert conn.ident == get_app_connection_ident(123, "testorg", API_URL, permissions)
    assert conn.ident != get_app_connection_ident(123, "testorg", API_URL)
