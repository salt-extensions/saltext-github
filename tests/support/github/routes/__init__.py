"""
Route mixins implementing the consumed GitHub API surface, grouped per area.
"""

from tests.support.github.routes.milestones import MilestoneRoutes
from tests.support.github.routes.orgs import OrgRoutes
from tests.support.github.routes.repos import RepoRoutes
from tests.support.github.routes.rulesets import RulesetRoutes
from tests.support.github.routes.teams import TeamRoutes

__all__ = [
    "MilestoneRoutes",
    "OrgRoutes",
    "RepoRoutes",
    "RulesetRoutes",
    "TeamRoutes",
]
