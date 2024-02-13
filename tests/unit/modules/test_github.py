from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import salt.modules.config as config_module
import saltext.github.modules.github as github_module
from salt.exceptions import CommandExecutionError


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__opts__": {
            "valid": {"there": "found"},
            "github": {
                "token": "abc1234",
                "org_name": "my_organization",
                "repo_name": "my_repo",
                "allow_repo_privacy_changes": False,
            },
        },
        "__salt__": {"config.option": config_module.option},
    }
    return {
        config_module: module_globals,
        github_module: module_globals,
    }


def test__get_config_value_bad_profile():
    with pytest.raises(CommandExecutionError):
        github_module._get_config_value("not_there", "didnt_get_here")


def test__get_config_value_bad_config_name():
    with pytest.raises(CommandExecutionError):
        github_module._get_config_value("valid", "not_there")


def test__get_config_value():
    ret = github_module._get_config_value("valid", "there")
    assert ret == "found"


def test__get_client():
    mock_client = MagicMock()
    assert not github_module.__context__
    with patch("github.Github", mock_client):
        github_module._get_client("github")
        mock_client.assert_called_with("abc1234", per_page=100)
    assert "github.abc1234:my_organization" in github_module.__context__
