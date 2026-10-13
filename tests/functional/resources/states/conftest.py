import copy

import pytest
import salt.loader

from tests.functional.resources.conftest import RTYPE


@pytest.fixture(scope="module")
def res_state_opts(res_opts):
    opts = copy.deepcopy(res_opts)
    opts["resource_type"] = RTYPE
    return opts


@pytest.fixture(scope="module")
def res_states(res_state_opts, res_modules, utils_loader, loader_context):
    return salt.loader.states(
        res_state_opts,
        res_modules,
        utils_loader,
        salt.loader.serializers(res_state_opts),
        context=loader_context,
        loaded_base_name=f"{__name__}.resstates",
    )


@pytest.fixture(params=(False, True))
def testmode(request, res_states):
    """
    Toggle ``__opts__["test"]`` inside the loaded state modules. The
    loader copies opts at construction time, so the packed dict is
    mutated directly.
    """
    packed_opts = res_states.pack["__opts__"]
    old = packed_opts.get("test", False)
    packed_opts["test"] = request.param
    try:
        yield request.param
    finally:
        packed_opts["test"] = old
