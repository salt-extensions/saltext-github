"""
Fixtures for testing the ``github`` resource type.

The salt-factories ``Loaders`` helper only builds classic minion
loaders, so the resource loaders (connection module, per-type execution
and state modules) are constructed by hand via ``salt.loader.resource``
and ``salt.loader.resource_modules``.
"""

import contextlib
import copy
import os

import pytest
import salt.loader
import salt.loader.context as loader_ctx
from salt.version import __version_info__ as _SALT_VERSION

# Salt version in test venv
if os.environ.get("SALT_REQUIREMENT") == "salt==master":
    SALT_VERSION = (_SALT_VERSION[0] + 1, 0)
else:
    SALT_VERSION = tuple(_SALT_VERSION)

if SALT_VERSION < (3008, 3):
    pytest.skip(reason="Resource modules require Salt >=3008.3")

RTYPE = "github"


@pytest.fixture(autouse=True)
def reset_loaders_state():
    """
    Shadow the parent conftest's autouse fixture of the same name so the
    classic factories loaders are not built for resource tests.
    """
    yield


@pytest.fixture(scope="module")
def resource_decl():
    """
    The ``github`` entry of the resource pillar subtree. Override per
    module to test owners/repos/exclude/include_archived handling.
    """
    return {"profile": "github"}


@pytest.fixture(scope="module")
def res_opts(minion_opts, resource_decl):
    opts = copy.deepcopy(minion_opts)
    opts["pillar"] = {"resources": {RTYPE: resource_decl}}
    return opts


@pytest.fixture(scope="module")
def loader_context():
    return {}


@pytest.fixture(autouse=True)
def _fresh_loader_context(loader_context):
    """
    The fake API state resets per test, so cached connections (and their
    repository caches) must be dropped alongside.
    """
    try:
        yield
    finally:
        loader_context.clear()


@pytest.fixture(scope="module")
def utils_loader(res_opts):
    return salt.loader.utils(res_opts)


@pytest.fixture(scope="module")
def resource_funcs(res_opts, utils_loader, loader_context):
    return salt.loader.resource(
        res_opts,
        utils=utils_loader,
        context=loader_context,
        loaded_base_name=f"{__name__}.resource",
    )


@pytest.fixture(scope="module")
def res_modules(res_opts, resource_funcs, utils_loader, loader_context):
    return salt.loader.resource_modules(
        res_opts,
        RTYPE,
        resource_funcs=resource_funcs,
        utils=utils_loader,
        context=loader_context,
        loaded_base_name=f"{__name__}.resmods",
    )


@pytest.fixture
def for_resource():
    """
    Context manager setting ``__resource__`` for the duration of a call,
    mirroring what the minion's dispatch does.
    """

    @contextlib.contextmanager
    def _set(rid, rtype=RTYPE):
        token = loader_ctx.resource_ctxvar.set({"id": rid, "type": rtype})
        try:
            yield
        finally:
            loader_ctx.resource_ctxvar.reset(token)

    return _set
