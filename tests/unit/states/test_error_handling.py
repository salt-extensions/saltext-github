"""
Ensure every public state function catches ``CommandExecutionError``
raised by the layers below (execution modules, state cores, profile
resolution) and reports it as a failed state instead of a traceback.
"""

import contextlib
import inspect
import re
from unittest import mock

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.resources.github.states import actions as res_actions
from saltext.github.resources.github.states import deploy_key as res_deploy_key
from saltext.github.resources.github.states import environment as res_environment
from saltext.github.resources.github.states import label as res_label
from saltext.github.resources.github.states import pages as res_pages
from saltext.github.resources.github.states import repo as res_repo
from saltext.github.resources.github.states import ruleset as res_ruleset
from saltext.github.states import github as github_mod
from saltext.github.states import github_org as github_org_mod
from saltext.github.states import github_repo as github_repo_mod
from saltext.github.utils.gh import resource as gh_resource

ERROR_MESSAGE = "something went wrong below the state layer"

MODULES = {
    "github": github_mod,
    "github_org": github_org_mod,
    "github_repo": github_repo_mod,
    "resources.actions": res_actions,
    "resources.deploy_key": res_deploy_key,
    "resources.environment": res_environment,
    "resources.label": res_label,
    "resources.pages": res_pages,
    "resources.repo": res_repo,
    "resources.ruleset": res_ruleset,
}

# Values for required parameters that are validated before any API call
REQUIRED_ARG_VALUES = {
    "ruleset_type": "repo",
}

# github.repo_absent interprets a raising ``get_repo_info`` as a missing
# repository (the module layer raises for 404s), so the injected error
# maps to a fulfilled state instead of a failed one.
EXPECTED_OVERRIDES = {
    ("github", "repo_absent"): {
        "name": "state-name",
        "changes": {},
        "result": True,
        "comment": "Repo state-name does not exist",
    },
}


def _public_funcs(mod):
    return sorted(
        name
        for name, func in inspect.getmembers(mod, inspect.isfunction)
        if not name.startswith("_") and func.__module__ == mod.__name__
    )


def _raising_salt_funcs(mod):
    """
    All ``__salt__`` functions a module calls, each raising. Includes
    calls made by the shared resource helpers, which are namespaced
    into the resource modules.
    """
    source = inspect.getsource(mod) + inspect.getsource(gh_resource)
    return {
        salt_func: mock.MagicMock(side_effect=CommandExecutionError(ERROR_MESSAGE))
        for salt_func in set(re.findall(r'__salt__\[\s*"([^"]+)"\s*\]', source))
    }


CASES = [
    pytest.param(mod_name, func_name, id=f"{mod_name}.{func_name}")
    for mod_name, mod in MODULES.items()
    for func_name in _public_funcs(mod)
]


@pytest.fixture
def configure_loader_modules():
    return {
        mod: {
            "__salt__": _raising_salt_funcs(mod),
            "__opts__": {"test": False},
            "__context__": {},
        }
        for mod in MODULES.values()
    }


@pytest.fixture(autouse=True)
def raising_gh_profile():
    """
    Make connection/profile resolution fail for state modules that
    call the utils directly instead of going through ``__salt__``.
    """
    gh_profile_mock = mock.MagicMock()
    gh_profile_mock.get_conn.side_effect = CommandExecutionError(ERROR_MESSAGE)
    gh_profile_mock.resource_conn.side_effect = CommandExecutionError(ERROR_MESSAGE)
    gh_profile_mock.get_config_value.side_effect = CommandExecutionError(ERROR_MESSAGE)
    with contextlib.ExitStack() as stack:
        for mod in MODULES.values():
            if hasattr(mod, "gh_profile"):
                stack.enter_context(mock.patch.object(mod, "gh_profile", gh_profile_mock))
        yield


@pytest.mark.parametrize("mod_name,func_name", CASES)
def test_state_funcs_catch_command_execution_errors(mod_name, func_name):
    func = getattr(MODULES[mod_name], func_name)
    kwargs = {
        param.name: REQUIRED_ARG_VALUES.get(param.name, "dummy")
        for param in inspect.signature(func).parameters.values()
        if param.name != "name"
        and param.default is inspect.Parameter.empty
        and param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
    }

    ret = func("state-name", **kwargs)

    assert ret == EXPECTED_OVERRIDES.get(
        (mod_name, func_name),
        {
            "name": "state-name",
            "changes": {},
            "result": False,
            "comment": ERROR_MESSAGE,
        },
    )
