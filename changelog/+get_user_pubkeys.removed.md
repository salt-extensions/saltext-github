Removed the unauthenticated ``get_user_pubkeys`` helper from ``saltext.github.utils.gh``. It ignored the configured ``api_url``, relied on ``salt.utils.http`` and was not exposed in any module
