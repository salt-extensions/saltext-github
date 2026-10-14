"""
Apply states to the targeted repository.

.. versionadded:: 1.1.0

Salt's per-resource execution loader is deny-by-default, so a resource
type must provide the ``state`` slot itself for ``state.apply`` and
friends to be dispatchable to its resources. This module re-exports the
stock :py:mod:`state <salt.modules.state>` execution module into the
per-type loader via ``namespaced_function`` (the pattern recommended in
Salt's resource state-authoring docs). The state engine then compiles
and runs on the managing minion while every module call inside the
rendered states dispatches through the per-resource loader — and thus
through this extension's ``resources/github/states/`` overrides.

Unlike the ``ssh`` resource type, no custom transport is needed: the
GitHub API is reachable from the managing minion, so the stock
implementations work unchanged. Only a few helpers that assume
managing-minion dunders (``__pillar__``, grains-backed state disabling)
are overridden below.
"""

import inspect
import logging

import salt.modules.state as _stock
from salt.utils.functools import namespaced_function

log = logging.getLogger(__name__)

__func_alias__ = {"apply_": "apply"}

# Only these functions are exposed as ``state.*`` for the github
# resource type. Everything else from the stock module is namespaced
# below purely so internal helper calls resolve against this module's
# (loader-packed) globals, but stays unexposed. Notably absent:
# queue/pause plumbing, ``disable``/``enable`` (grains-backed),
# ``pkg`` (salt-thin transport) and ``event``.
__load__ = [
    "apply_",
    "highstate",
    "id_exists",
    "running",
    "show_highstate",
    "show_low_sls",
    "show_lowstate",
    "show_sls",
    "show_states",
    "show_top",
    "single",
    "sls",
    "sls_exists",
    "sls_id",
    "test",
    "top",
]


def _namespace_stock():
    """
    Re-export every function defined in the stock module under this
    module's globals. The public entry points call module-level helpers
    (``_check_queue``, ``_get_test_value``, …) which access ``__salt__``
    and friends — those helpers must be namespaced too, or they would
    resolve dunders against the raw (unpacked) ``salt.modules.state``
    module and fail with a ``NameError``.
    """
    for fname, func in list(vars(_stock).items()):
        if inspect.isfunction(func) and func.__module__ == _stock.__name__:
            globals()[fname] = namespaced_function(func, globals())


_namespace_stock()


# ---------------------------------------------------------------------------
# Resource-context adjustments. Defined after the re-export so they
# shadow the stock implementations.
# ---------------------------------------------------------------------------


def _get_initial_pillar(opts):
    """
    Use the managing minion's in-memory pillar when it matches the
    requested pillarenv.

    The stock implementation reads ``__pillar__``, which is not packed
    into per-resource loaders. The managing minion's pillar contains the
    resource declarations anyway, and reusing it avoids recompiling
    pillar once per targeted repository.
    """
    pillar = __opts__.get("pillar")
    if pillar and opts.get("pillarenv") == __opts__.get("pillarenv"):
        try:
            return pillar.value()
        except AttributeError:
            return pillar
    return None


def _get_pillar_errors(kwargs, pillar=None):
    """
    Stock implementation minus the in-memory ``__pillar__`` fallback,
    which is not packed into per-resource loaders.
    """
    if kwargs.get("force"):
        return None
    return (pillar or {}).get("_errors")


def _disabled(funs):  # pylint: disable=unused-argument
    """
    ``state.disable``/``state.enable`` (grains-backed) are not exposed
    for the github resource type, so state runs can never be disabled.
    """
    return []
