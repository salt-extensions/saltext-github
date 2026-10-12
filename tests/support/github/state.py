"""
Global dict-backed store of the fake GitHub API.
"""

# pyright: reportImportCycles=false  (type-only cycle with .entities, see there)

from collections import defaultdict
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field

from tests.support.github.entities import DeployKey
from tests.support.github.entities import DeployKeyData
from tests.support.github.entities import Entity
from tests.support.github.entities import EntityData
from tests.support.github.entities import Environment
from tests.support.github.entities import EnvironmentData
from tests.support.github.entities import Issue
from tests.support.github.entities import IssueData
from tests.support.github.entities import Label
from tests.support.github.entities import LabelData
from tests.support.github.entities import Member
from tests.support.github.entities import MemberData
from tests.support.github.entities import Milestone
from tests.support.github.entities import MilestoneData
from tests.support.github.entities import NotFound
from tests.support.github.entities import Organization
from tests.support.github.entities import OrganizationData
from tests.support.github.entities import OrgName
from tests.support.github.entities import OrgRulesetData
from tests.support.github.entities import Pages
from tests.support.github.entities import PagesData
from tests.support.github.entities import PullRequest
from tests.support.github.entities import PullRequestData
from tests.support.github.entities import Repo
from tests.support.github.entities import RepoData
from tests.support.github.entities import RepoId
from tests.support.github.entities import RepoRulesetData
from tests.support.github.entities import Ruleset
from tests.support.github.entities import Secret
from tests.support.github.entities import SecretData
from tests.support.github.entities import Team
from tests.support.github.entities import TeamData
from tests.support.github.entities import TeamName
from tests.support.github.entities import User
from tests.support.github.entities import UserData
from tests.support.github.entities import UserName


@dataclass
class GlobalState:  # pylint: disable=too-many-instance-attributes
    base_url: str = field(init=False, default="")
    orgs: dict[OrgName, OrganizationData] = field(default_factory=dict)
    users: dict[UserName, UserData] = field(default_factory=dict)
    repos: dict[RepoId, RepoData] = field(default_factory=dict)
    members: dict[tuple[OrgName, UserName], MemberData] = field(default_factory=dict)
    teams: dict[tuple[OrgName, TeamName], TeamData] = field(default_factory=dict)
    rulesets_org: dict[OrgName, dict[int, OrgRulesetData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    rulesets_repo: dict[RepoId, dict[int, RepoRulesetData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    milestones: dict[RepoId, dict[int, MilestoneData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    issues: dict[RepoId, dict[int, IssueData]] = field(default_factory=lambda: defaultdict(dict))
    pulls: dict[RepoId, dict[int, PullRequestData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    deploy_keys: dict[RepoId, dict[int, DeployKeyData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    secrets: dict[RepoId, dict[str, SecretData]] = field(default_factory=lambda: defaultdict(dict))
    environments: dict[RepoId, dict[str, EnvironmentData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    labels: dict[RepoId, dict[str, LabelData]] = field(default_factory=lambda: defaultdict(dict))
    pages: dict[RepoId, PagesData] = field(default_factory=dict)

    def __post_init__(self):
        self.snapshot()

    def snapshot(self):
        self._init_orgs = deepcopy(self.orgs)
        self._init_users = deepcopy(self.users)
        self._init_repos = deepcopy(self.repos)
        self._init_members = deepcopy(self.members)
        self._init_teams = deepcopy(self.teams)
        self._init_rulesets_org = deepcopy(self.rulesets_org)
        self._init_rulesets_repo = deepcopy(self.rulesets_repo)
        self._init_milestones = deepcopy(self.milestones)
        self._init_issues = deepcopy(self.issues)
        self._init_pulls = deepcopy(self.pulls)
        self._init_deploy_keys = deepcopy(self.deploy_keys)
        self._init_secrets = deepcopy(self.secrets)
        self._init_environments = deepcopy(self.environments)
        self._init_labels = deepcopy(self.labels)
        self._init_pages = deepcopy(self.pages)

    def reset(self):
        self.orgs = {}
        self.users = {}
        self.repos = {}
        self.members = {}
        self.teams = {}
        self.rulesets_org = defaultdict(dict)
        self.rulesets_repo = defaultdict(dict)
        self.milestones = defaultdict(dict)
        self.issues = defaultdict(dict)
        self.pulls = defaultdict(dict)
        self.deploy_keys = defaultdict(dict)
        self.secrets = defaultdict(dict)
        self.environments = defaultdict(dict)
        self.labels = defaultdict(dict)
        self.pages = {}
        self._init_orgs = {}
        self._init_users = {}
        self._init_repos = {}
        self._init_members = {}
        self._init_teams = {}
        self._init_rulesets_org = defaultdict(dict)
        self._init_rulesets_repo = defaultdict(dict)
        self._init_milestones = defaultdict(dict)
        self._init_issues = defaultdict(dict)
        self._init_pulls = defaultdict(dict)
        self._init_deploy_keys = defaultdict(dict)
        self._init_secrets = defaultdict(dict)
        self._init_environments = defaultdict(dict)
        self._init_labels = defaultdict(dict)
        self._init_pages = {}

    def restore(self):
        self.orgs = deepcopy(self._init_orgs)
        self.users = deepcopy(self._init_users)
        self.repos = deepcopy(self._init_repos)
        self.members = deepcopy(self._init_members)
        self.teams = deepcopy(self._init_teams)
        self.rulesets_org = deepcopy(self._init_rulesets_org)
        self.rulesets_repo = deepcopy(self._init_rulesets_repo)
        self.milestones = deepcopy(self._init_milestones)
        self.issues = deepcopy(self._init_issues)
        self.pulls = deepcopy(self._init_pulls)
        self.deploy_keys = deepcopy(self._init_deploy_keys)
        self.secrets = deepcopy(self._init_secrets)
        self.environments = deepcopy(self._init_environments)
        self.labels = deepcopy(self._init_labels)
        self.pages = deepcopy(self._init_pages)

    def _next_issue_number(self, repo_id: RepoId) -> int:
        # Issues and pull requests share one number sequence per repo.
        return len(self.issues[repo_id]) + len(self.pulls[repo_id]) + 1

    def add_user(self, name: str, **params) -> User:
        user = UserData(name, **params)
        if user.login in self.users:
            raise RuntimeError(f"User {user.login} already exists")
        self.users[user.login] = user
        return User(self, user)

    def add_org(self, name: str, **params) -> Organization:
        org = OrganizationData(name, **params)
        if org.login in self.orgs:
            raise RuntimeError(f"Organization {org.login} already exists")
        self.orgs[org.login] = org
        return Organization(self, org)

    def get_user(self, login: str, *, exc=NotFound) -> User:
        if login not in self.users:
            raise exc(f"Requested nonexistent user {login=}")
        return User(self, self.users[login])

    def get_org(self, login: str, *, exc=NotFound) -> Organization:
        if login not in self.orgs:
            raise exc(f"Requested nonexistent org {login=}")
        return Organization(self, self.orgs[login])

    def get_org_id(self, org_id: int | str, *, exc=NotFound) -> Organization:
        org_id = int(org_id)
        res = next((org for org in self.orgs.values() if org.id == org_id), None)
        if res is None:
            raise exc(f"Requested nonexistent org_id {org_id=}")
        return Organization(self, res)

    def get_repo(self, repo_id: RepoId | Sequence[str] | str, *, exc=NotFound) -> Repo:
        if isinstance(repo_id, RepoId):
            resolved = repo_id
        elif isinstance(repo_id, str):
            resolved = RepoId.from_str(repo_id)
        else:
            resolved = RepoId.from_seq(repo_id)

        if resolved.owner not in self.orgs:
            if resolved.owner in self.users:
                raise NotImplementedError
            raise exc(f"Requested repo from nonexistent org {resolved.owner=}")
        if resolved not in self.repos:
            raise exc(f"Requested nonexistent repo {resolved.name=} from org {resolved.owner=}")
        return Repo(self, self.repos[resolved])

    def add(self, entity: EntityData | Entity):  # pylint: disable=too-many-return-statements
        if isinstance(entity, Entity):
            data = entity.data
        else:
            data = entity

        if isinstance(data, RepoData):
            self.repos[data.repo_id] = data
            return Repo(self, data)
        if isinstance(data, MemberData):
            self.members[(data.org, data.login)] = data
            return Member(self, data)
        if isinstance(data, TeamData):
            self.teams[(data.org, data.slug)] = data
            return Team(self, data)
        if isinstance(data, RepoRulesetData):
            assert data.source in self.repos
            self.rulesets_repo[data.source][data.id] = data
            return Ruleset(self, data)
        if isinstance(data, OrgRulesetData):
            assert data.source in self.orgs
            self.rulesets_org.setdefault(data.source, {})[data.id] = data
            return Ruleset(self, data)
        if isinstance(data, DeployKeyData):
            assert data.repo in self.repos
            self.deploy_keys[data.repo][data.id] = data
            return DeployKey(self, data)
        if isinstance(data, SecretData):
            assert data.repo in self.repos
            self.secrets[data.repo][data.name] = data
            return Secret(self, data)
        if isinstance(data, EnvironmentData):
            assert data.repo in self.repos
            self.environments[data.repo][data.name] = data
            return Environment(self, data)
        if isinstance(data, LabelData):
            assert data.repo in self.repos
            self.labels[data.repo][data.name] = data
            return Label(self, data)
        if isinstance(data, PagesData):
            assert data.repo in self.repos
            self.pages[data.repo] = data
            return Pages(self, data)
        if isinstance(data, MilestoneData):
            if data.number < 0:
                data = data.with_(number=len(self.milestones[data.repo]) + 1)
            self.milestones[data.repo][data.number] = data
            return Milestone(self, data)
        if isinstance(data, IssueData):
            if data.number < 0:
                data = data.with_(number=self._next_issue_number(data.repo))
            self.issues[data.repo][data.number] = data
            return Issue(self, data)
        if isinstance(data, PullRequestData):
            if data.number < 0:
                data = data.with_(number=self._next_issue_number(data.repo))
            self.pulls[data.repo][data.number] = data
            return PullRequest(self, data)
        if isinstance(data, UserData):
            self.users[data.login] = data
            return User(self, data)
        if isinstance(data, OrganizationData):
            self.orgs[data.login] = data
            return Organization(self, data)
        raise TypeError(f"Unknown object: {data=}")

    def replace(self, old: EntityData | Entity, new: EntityData | Entity):
        if isinstance(old, Entity):
            old_data = old.data
        else:
            old_data = old
        if isinstance(new, Entity):
            new_data = new.data
        else:
            new_data = new
        assert type(old_data) is type(new_data)
        if isinstance(old_data, RepoData):
            self.repos.pop(old_data.repo_id)
        elif isinstance(old_data, MemberData):
            self.members.pop((old_data.org, old_data.login))
        elif isinstance(old_data, TeamData):
            self.teams.pop((old_data.org, old_data.slug))
        elif isinstance(old_data, RepoRulesetData):
            self.rulesets_repo[old_data.source].pop(old_data.id)
        elif isinstance(old_data, OrgRulesetData):
            self.rulesets_org[old_data.source].pop(old_data.id)
        elif isinstance(old_data, DeployKeyData):
            self.deploy_keys[old_data.repo].pop(old_data.id)
        elif isinstance(old_data, SecretData):
            self.secrets[old_data.repo].pop(old_data.name)
        elif isinstance(old_data, EnvironmentData):
            self.environments[old_data.repo].pop(old_data.name)
        elif isinstance(old_data, LabelData):
            self.labels[old_data.repo].pop(old_data.name)
        elif isinstance(old_data, PagesData):
            self.pages.pop(old_data.repo)
        elif isinstance(old_data, MilestoneData):
            self.milestones[old_data.repo].pop(old_data.number)
        elif isinstance(old_data, IssueData):
            self.issues[old_data.repo].pop(old_data.number)
        elif isinstance(old_data, PullRequestData):
            self.pulls[old_data.repo].pop(old_data.number)
        elif isinstance(old_data, UserData):
            self.users.pop(old_data.login)
        elif isinstance(old_data, OrganizationData):
            self.orgs.pop(old_data.login)
        else:
            raise TypeError(f"Unknown object: {old_data=}")
        return self.add(new_data)
