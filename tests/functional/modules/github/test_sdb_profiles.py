"""
Verify that profile configuration values can be sourced from SDB URIs,
e.g. environment variables via the ``env`` driver (useful in CI).

Values in the minion configuration are rendered by Salt itself when the
configuration is loaded, hence the environment variable needs to be set
before the minion options are built. Access-time rendering (which covers
pillar-sourced profiles) is exercised in the unit tests.
"""

import pytest


@pytest.fixture(scope="module")
def github_token_env(github_profile):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GITHUB_TOKEN", github_profile["token"])
        yield


@pytest.fixture(scope="module")
def minion_config_defaults(github_profile, github_token_env):  # pylint: disable=unused-argument
    profile = dict(github_profile)
    profile["token"] = "sdb://osenv/GITHUB_TOKEN"
    return {
        "github": profile,
        "osenv": {"driver": "env"},
    }


def test_profile_values_resolve_sdb_uris(github):
    # The fake GitHub API server rejects requests carrying an invalid token,
    # so this only passes if the SDB URI was rendered.
    assert set(github.list_repos()) == {"repo-a", "repo-b"}
