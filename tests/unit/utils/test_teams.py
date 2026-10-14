from unittest.mock import MagicMock

import pytest

from saltext.github.utils.gh import teams as gh_teams
from saltext.github.utils.gh.exceptions import GitHubApiError


def test_add_repo_raises_on_permission_update_failure():
    conn = MagicMock()
    team = conn.get_org.return_value.get_team_by_slug.return_value
    team.update_team_repository.return_value = False
    with pytest.raises(
        GitHubApiError, match="Failed setting permission push on repo repo for team Team A"
    ):
        gh_teams.add_repo(conn, {"slug": "team-a", "name": "Team A"}, "repo", permission="push")
