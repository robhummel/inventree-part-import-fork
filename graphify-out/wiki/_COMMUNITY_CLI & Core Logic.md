---
type: community
members: 7
---

# CLI & Core Logic

**Members:** 7 nodes

## Members
- [[DryInvenTreeAPI]] - code - inventree_part_import/cli.py
- [[PartImporter]] - code - inventree_part_import/part_importer.py
- [[RetryInvenTreeAPI]] - code - inventree_part_import/retries.py
- [[Safety via Dry Run]] - document - README.md
- [[inventree_part_import]] - code - inventree_part_import/cli.py
- [[setup_categories_and_parameters]] - code - inventree_part_import/categories.py
- [[setup_inventree_api]] - code - inventree_part_import/config/__init__.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/CLI_&_Core_Logic
SORT file.name ASC
```

## Connections to other communities
- 3 edges to [[_COMMUNITY_Supplier Base & Hooks]]
- 2 edges to [[_COMMUNITY_Custom Exceptions]]
- 1 edge to [[_COMMUNITY_CLI Integration Tests]]

## Top bridge nodes
- [[PartImporter]] - degree 5, connects to 2 communities
- [[inventree_part_import]] - degree 4, connects to 1 community
- [[setup_inventree_api]] - degree 4, connects to 1 community
- [[setup_categories_and_parameters]] - degree 2, connects to 1 community