---
type: community
members: 5
---

# CLI Integration Tests

**Members:** 5 nodes

## Members
- [[.setup_class()]] - code - tests/test_cli.py
- [[.test_setup_categories()]] - code - tests/test_cli.py
- [[TestCli]] - code - tests/test_cli.py
- [[test_cli.py]] - code - tests/test_cli.py
- [[test_config_dir_override()]] - code - tests/test_cli.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/CLI_Integration_Tests
SORT file.name ASC
```

## Connections to other communities
- 1 edge to [[_COMMUNITY_CLI & Core Logic]]

## Top bridge nodes
- [[TestCli]] - degree 4, connects to 1 community