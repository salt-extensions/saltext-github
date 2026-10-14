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
def minion_funcs(res_opts, utils_loader, loader_context):
    """
    The managing minion's module loader, packed as the ``__minion__``
    escape hatch like the state engine does in resource context.
    """
    return salt.loader.minion_mods(
        res_opts,
        loader_context,
        utils=utils_loader,
        loaded_base_name=f"{__name__}.minionmods",
    )


@pytest.fixture(scope="module")
def res_states(res_state_opts, res_modules, utils_loader, loader_context, minion_funcs):
    return salt.loader.states(
        res_state_opts,
        res_modules,
        utils_loader,
        salt.loader.serializers(res_state_opts),
        context=loader_context,
        minion_mods=minion_funcs,
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
