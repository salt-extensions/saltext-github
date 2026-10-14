"""
Routes: API metadata (rate limit).
"""

from tests.support.github.base import APIBase
from tests.support.github.routing import GET

RATE_LIMIT_RESOURCES = {
    name: {"limit": limit, "used": 42, "remaining": limit - 42, "reset": 1760000000}
    for name, limit in (("core", 5000), ("search", 30), ("graphql", 5000))
}


class MetaRoutes(APIBase):
    @GET("rate_limit")
    def _rate_limit(self, _match, _query, _body):
        # The top-level "rate" key is GitHub's deprecated alias for
        # resources.core.
        return 200, {
            "resources": RATE_LIMIT_RESOURCES,
            "rate": RATE_LIMIT_RESOURCES["core"],
        }
