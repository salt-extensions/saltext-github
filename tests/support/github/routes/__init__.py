"""
Route mixins implementing the consumed GitHub API surface, grouped per area.
"""

from tests.support.github.routes.actions import ActionsRoutes
from tests.support.github.routes.deploy_keys import DeployKeyRoutes
from tests.support.github.routes.environments import EnvironmentRoutes
from tests.support.github.routes.issues import IssueRoutes
from tests.support.github.routes.labels import LabelRoutes
from tests.support.github.routes.meta import MetaRoutes
from tests.support.github.routes.milestones import MilestoneRoutes
from tests.support.github.routes.orgs import OrgRoutes
from tests.support.github.routes.pages import PagesRoutes
from tests.support.github.routes.repos import RepoRoutes
from tests.support.github.routes.rulesets import RulesetRoutes
from tests.support.github.routes.teams import TeamRoutes

__all__ = [
    "ActionsRoutes",
    "DeployKeyRoutes",
    "EnvironmentRoutes",
    "IssueRoutes",
    "LabelRoutes",
    "MetaRoutes",
    "MilestoneRoutes",
    "OrgRoutes",
    "PagesRoutes",
    "RepoRoutes",
    "RulesetRoutes",
    "TeamRoutes",
]
