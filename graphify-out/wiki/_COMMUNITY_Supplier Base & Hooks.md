---
type: community
members: 10
---

# Supplier Base & Hooks

**Members:** 10 nodes

## Members
- [[ApiPart]] - code - inventree_part_import/suppliers/base.py
- [[DigiKey]] - code - inventree_part_import/suppliers/supplier_digikey.py
- [[LCSC]] - code - inventree_part_import/suppliers/supplier_lcsc.py
- [[Mouser]] - code - inventree_part_import/suppliers/supplier_mouser.py
- [[Pre Creation Hooks (hooks.py)]] - document - README.md
- [[Reichelt]] - code - inventree_part_import/suppliers/supplier_reichelt.py
- [[Supplier]] - code - inventree_part_import/suppliers/base.py
- [[SupplierError]] - code - inventree_part_import/exceptions.py
- [[SupplierLoadError]] - code - inventree_part_import/exceptions.py
- [[TME]] - code - inventree_part_import/suppliers/supplier_tme.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Supplier_Base_&_Hooks
SORT file.name ASC
```

## Connections to other communities
- 4 edges to [[_COMMUNITY_Custom Exceptions]]
- 3 edges to [[_COMMUNITY_CLI & Core Logic]]

## Top bridge nodes
- [[ApiPart]] - degree 10, connects to 1 community
- [[SupplierError]] - degree 8, connects to 1 community
- [[Supplier]] - degree 8, connects to 1 community
- [[SupplierLoadError]] - degree 4, connects to 1 community