``saltext-github``: Integrate Salt with GitHub
==============================================

Salt Extension for interacting with GitHub:

* Manage organization members, teams and organization rulesets via the
  :py:mod:`github_org <saltext.github.modules.github_org>` execution and
  state modules.
* List, create and manage organization- or user-owned repositories –
  including their settings, teams, rulesets, deploy keys, Actions secrets
  and workflow permissions, environments, labels and Pages sites – and
  query their issues, milestones and pull requests via the
  :py:mod:`github_repo <saltext.github.modules.github_repo>` execution
  and state modules.
* Works against GitHub Enterprise Server instances via the
  :ghconf:`api_url` profile parameter.

.. toctree::
  :maxdepth: 2
  :caption: Guides
  :hidden:

  topics/installation
  topics/configuration

.. toctree::
  :maxdepth: 2
  :caption: Provided Modules
  :hidden:

  ref/modules/index
  ref/states/index
  ref/utils/index

.. toctree::
  :maxdepth: 2
  :caption: Reference
  :hidden:

  changelog


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
