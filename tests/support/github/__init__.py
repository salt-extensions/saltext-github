"""
A stateful fake GitHub API server for functional tests.

The server implements the subset of the GitHub REST API that this extension
consumes, backed by plain dicts. It allows exercising the execution and state
modules end-to-end (idempotence, drift detection, test mode) without network
access or mocking individual functions.

Layout:

:mod:`~tests.support.github.entities`
    Typed entity model (``*Data`` storage dataclasses + hydrated wrappers),
    ``EntityView``, ``NotFound``.
:mod:`~tests.support.github.state`
    ``GlobalState`` — the dict-backed store with snapshot/restore.
:mod:`~tests.support.github.routing`
    Route declaration decorators (``GET``/``POST``/...) and ``Request``.
:mod:`~tests.support.github.base`
    ``APIBase`` — dispatch, shared resolvers, request log, HTTP plumbing.
:mod:`~tests.support.github.routes`
    Per-area route mixins composed into :class:`FakeGitHubAPI` below.
"""

from tests.support.github.base import APP_ID
from tests.support.github.base import APP_INSTALLATION_ID
from tests.support.github.base import APP_TOKEN_PREFIX
from tests.support.github.base import APP_USER_INSTALLATION_ID
from tests.support.github.base import DEPLOY_KEY_A
from tests.support.github.base import DEPLOY_KEY_B
from tests.support.github.base import ORG
from tests.support.github.base import TOKEN
from tests.support.github.base import USER_KEY_A
from tests.support.github.base import USER_KEY_B
from tests.support.github.entities import BranchPolicy
from tests.support.github.entities import DeployKey
from tests.support.github.entities import Entity
from tests.support.github.entities import EntityData
from tests.support.github.entities import EntityView
from tests.support.github.entities import Environment
from tests.support.github.entities import Issue
from tests.support.github.entities import IssueComment
from tests.support.github.entities import Label
from tests.support.github.entities import Member
from tests.support.github.entities import Milestone
from tests.support.github.entities import NotFound
from tests.support.github.entities import Organization
from tests.support.github.entities import Pages
from tests.support.github.entities import PullRequest
from tests.support.github.entities import Repo
from tests.support.github.entities import RepoFile
from tests.support.github.entities import RepoId
from tests.support.github.entities import Ruleset
from tests.support.github.entities import Secret
from tests.support.github.entities import Team
from tests.support.github.entities import TeamMember
from tests.support.github.entities import User
from tests.support.github.routes import ActionsRoutes
from tests.support.github.routes import AppRoutes
from tests.support.github.routes import ContentsRoutes
from tests.support.github.routes import DeployKeyRoutes
from tests.support.github.routes import EnvironmentRoutes
from tests.support.github.routes import IssueRoutes
from tests.support.github.routes import LabelRoutes
from tests.support.github.routes import MetaRoutes
from tests.support.github.routes import MilestoneRoutes
from tests.support.github.routes import OrgRoutes
from tests.support.github.routes import PagesRoutes
from tests.support.github.routes import RepoRoutes
from tests.support.github.routes import RulesetRoutes
from tests.support.github.routes import TeamRoutes
from tests.support.github.routing import Request
from tests.support.github.state import GlobalState

__all__ = [
    "APP_ID",
    "APP_INSTALLATION_ID",
    "APP_TOKEN_PREFIX",
    "APP_USER_INSTALLATION_ID",
    "DEPLOY_KEY_A",
    "DEPLOY_KEY_B",
    "ORG",
    "TOKEN",
    "USER_KEY_A",
    "USER_KEY_B",
    "BranchPolicy",
    "DeployKey",
    "Entity",
    "EntityData",
    "EntityView",
    "Environment",
    "FakeGitHubAPI",
    "GlobalState",
    "Issue",
    "IssueComment",
    "Label",
    "Member",
    "Milestone",
    "NotFound",
    "Organization",
    "Pages",
    "PullRequest",
    "Repo",
    "RepoFile",
    "RepoId",
    "Request",
    "Ruleset",
    "Secret",
    "Team",
    "TeamMember",
    "User",
]


class FakeGitHubAPI(  # pylint: disable=too-many-ancestors
    OrgRoutes,
    RepoRoutes,
    TeamRoutes,
    RulesetRoutes,
    MilestoneRoutes,
    IssueRoutes,
    DeployKeyRoutes,
    ActionsRoutes,
    EnvironmentRoutes,
    LabelRoutes,
    PagesRoutes,
    MetaRoutes,
    ContentsRoutes,
    AppRoutes,
):
    """
    Dict-backed implementation of the consumed GitHub API surface.
    """
