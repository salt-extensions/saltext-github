"""
Inspect running jobs on the managing minion.

.. versionadded:: 1.1.0

The stock :py:mod:`state <salt.modules.state>` execution module
(re-exported for this resource type) performs conflict detection via
``saltutil.is_running``. State runs for resources execute inline on the
managing minion, so its job table is the correct one to consult. Both
functions only need ``__opts__``, so the stock implementations are
re-exported unchanged.
"""

import logging

import salt.modules.saltutil as _stock
from salt.utils.functools import namespaced_function

log = logging.getLogger(__name__)

running = namespaced_function(_stock.running, globals())
is_running = namespaced_function(_stock.is_running, globals())

__load__ = ["running", "is_running"]
