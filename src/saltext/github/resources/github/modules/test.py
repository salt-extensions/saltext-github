"""
Provide the ``test`` execution module for the ``github`` resource type.

.. versionadded:: 1.1.0

Its location in the per-type override directory makes it visible only
to the ``github`` resource loader, so no ``__virtual__`` gate is needed.
"""

import logging

log = logging.getLogger(__name__)


def ping():
    """
    Return whether the targeted repository is reachable via the API.

    Delegates to the connection module's ``ping()`` via
    ``__resource_funcs__`` so the result reflects the actual state of
    the resource rather than the managing minion.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' test.ping
    """
    return __resource_funcs__["github.ping"]()
