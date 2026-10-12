"""
Routes: repository environments and their deployment branch policies.
"""

from tests.support.github.base import APIBase
from tests.support.github.routing import DELETE
from tests.support.github.routing import GET
from tests.support.github.routing import POST
from tests.support.github.routing import PUT


class EnvironmentRoutes(APIBase):
    @GET("repos/<org>/<repo>/environments")
    def _list_environments(self, match, _query, _body):
        repo = self._resolve_repo(match)
        environments = [env.payload() for env in sorted(repo.environments, key=lambda x: x.name)]
        return 200, {"total_count": len(environments), "environments": environments}

    @GET("repos/<org>/<repo>/environments/<environment>")
    def _get_environment(self, match, _query, _body):
        repo = self._resolve_repo(match)
        return 200, repo.get_environment(match["environment"]).payload()

    @PUT("repos/<org>/<repo>/environments/<environment>")
    def _put_environment(self, match, _query, body):
        repo = self._resolve_repo(match)
        # Like the real API, a PUT replaces the full configuration,
        # so unsent settings are reset to their defaults.
        settings = {
            "wait_timer": (body or {}).get("wait_timer", 0),
            "prevent_self_review": (body or {}).get("prevent_self_review", False),
            "reviewers": (body or {}).get("reviewers") or [],
            "deployment_branch_policy": (body or {}).get("deployment_branch_policy"),
        }
        try:
            env = repo.get_environment(match["environment"])
        except KeyError:
            env = repo.add_environment(match["environment"], **settings)
        else:
            env = env.update(**settings)
        return 200, env.payload()

    @DELETE("repos/<org>/<repo>/environments/<environment>")
    def _delete_environment(self, match, _query, _body):
        repo = self._resolve_repo(match)
        repo.remove_environment(match["environment"])
        return 204

    @GET("repos/<org>/<repo>/environments/<environment>/deployment-branch-policies")
    def _list_branch_policies(self, match, _query, _body):
        repo = self._resolve_repo(match)
        env = repo.get_environment(match["environment"])
        policies = [policy.payload() for policy in sorted(env.branch_policies, key=lambda x: x.id)]
        return 200, {"total_count": len(policies), "branch_policies": policies}

    @POST("repos/<org>/<repo>/environments/<environment>/deployment-branch-policies")
    def _create_branch_policy(self, match, _query, body):
        repo = self._resolve_repo(match)
        env = repo.get_environment(match["environment"])
        policy = env.add_branch_policy(body["name"], type=body.get("type", "branch"))
        return 200, policy.payload()

    @DELETE("repos/<org>/<repo>/environments/<environment>/deployment-branch-policies/<policy_id>")
    def _delete_branch_policy(self, match, _query, _body):
        repo = self._resolve_repo(match)
        env = repo.get_environment(match["environment"])
        env.remove_branch_policy(match["policy_id"])
        return 204
