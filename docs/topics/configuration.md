(github-configuration)=
# Configuration

All modules provided by this extension read their configuration from
*profiles*. A profile is a mapping under a top-level key in the minion
configuration, minion pillar or master configuration. Functions and
states use the profile named `github` by default and accept a
`profile` argument to select a different one.

## Profile parameters

:::{ghconf} token
:::
`token`
: Required. Access token to authenticate with.

:::{ghconf} owner
:::
`owner`
: Default owner (organization or user) whose resources are managed.
  Defaults to the token's user, so organization management and tokens
  without an associated user account (e.g. GitHub App installation
  tokens) require it to be set. `org_name` is supported as a legacy
  alias.

  :::{versionadded} 1.1.0
  Renamed from `org_name`. The new {py:mod}`github_repo <saltext.github.modules.github_repo>`
  modules can manage user repositories in addition to organization ones.
  :::

:::{ghconf} repo_name
:::
`repo_name`
: The default repository the `github_repo` functions and states operate
  on when no `repo_name` is passed.

:::{ghconf} allow_repo_privacy_changes
:::
`allow_repo_privacy_changes`
: Allow automated repository privacy modifications. It can be dangerous
  to change the privacy of a repository in an automated way, hence this
  defaults to false.

:::{ghconf} api_url
:::
`api_url`
: Base URL of the GitHub API. Set this when targeting a GitHub
  Enterprise Server instance, e.g. `https://github.example.com/api/v3`.
  Defaults to `https://api.github.com`.

## Multiple profiles

Any number of profiles can be defined and selected per call:

```yaml
github:
  token: abc1234
  owner: my_organization

my_user:
  token: def5678
```

```bash
salt-call github_repo.list profile=my_user
```

## Secret management

Profile values containing [SDB URIs](https://docs.saltproject.io/en/latest/topics/sdb/index.html)
are rendered on access, which also works in pillar-sourced profiles:

```yaml
# Requires a corresponding SDB profile in the minion configuration, e.g.
#   osenv:
#     driver: env
github:
  token: sdb://osenv/GITHUB_TOKEN
  owner: my_organization
```
