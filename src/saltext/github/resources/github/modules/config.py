"""
Look up configuration values from the managing minion.

.. versionadded:: 1.1.0

Repositories have no minion configuration of their own — GitHub
profiles and related settings live on the managing minion. The stock
:py:mod:`state <salt.modules.state>` execution module (re-exported for
this resource type) relies on ``config.get``/``config.option``, so this
override provides them: it delegates to the managing minion's loader
when the ``__minion__`` escape hatch is packed (state-engine context)
and falls back to the managing minion's opts otherwise (the minion's
dispatch-context per-type loaders do not pack ``__minion__``).
"""

import logging

import salt.utils.data

log = logging.getLogger(__name__)


def _minion():
    try:
        return __minion__
    except NameError:
        return None


def get(key, default="", delimiter=":", omit_opts=False, **kwargs):
    """
    Look up a config value on the managing minion. See
    :py:func:`config.get <salt.modules.config.get>` for details.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' config.get state_verbose
    """
    minion = _minion()
    if minion is not None:
        return minion["config.get"](
            key, default=default, delimiter=delimiter, omit_opts=omit_opts, **kwargs
        )
    if omit_opts:
        return default
    return salt.utils.data.traverse_dict_and_list(__opts__, key, default, delimiter)


def option(value, default="", omit_opts=False, omit_all=False, **kwargs):
    """
    Return the value of a specific config option on the managing minion.
    See :py:func:`config.option <salt.modules.config.option>` for details.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' config.option state_queue
    """
    minion = _minion()
    if minion is not None:
        return minion["config.option"](
            value, default=default, omit_opts=omit_opts, omit_all=omit_all, **kwargs
        )
    if not (omit_opts or omit_all) and value in __opts__:
        return __opts__[value]
    return default
