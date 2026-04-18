# Graph Report - .  (2026-04-17)

## Corpus Check
- Corpus is ~11,698 words - fits in a single context window. You may not need a graph.

## Summary
- 48 nodes · 70 edges · 8 communities detected
- Extraction: 64% EXTRACTED · 36% INFERRED · 0% AMBIGUOUS · INFERRED: 25 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_InvenTree API Integration|InvenTree API Integration]]
- [[_COMMUNITY_Supplier Base & Hooks|Supplier Base & Hooks]]
- [[_COMMUNITY_Custom Exceptions|Custom Exceptions]]
- [[_COMMUNITY_CLI & Core Logic|CLI & Core Logic]]
- [[_COMMUNITY_CLI Integration Tests|CLI Integration Tests]]
- [[_COMMUNITY_Localization Support|Localization Support]]
- [[_COMMUNITY_Package Initialization|Package Initialization]]
- [[_COMMUNITY_Main Entrypoint|Main Entrypoint]]

## God Nodes (most connected - your core abstractions)
1. `ApiPart` - 10 edges
2. `InvenTreeObjectCreationError` - 8 edges
3. `SupplierError` - 8 edges
4. `Supplier` - 8 edges
5. `PartImporter` - 5 edges
6. `TestCli` - 4 edges
7. `inventree_part_import` - 4 edges
8. `InvenTreePartImportError` - 4 edges
9. `SupplierLoadError` - 4 edges
10. `LCSC` - 4 edges

## Surprising Connections (you probably didn't know these)
- `ApiPart` --conceptually_related_to--> `Pre Creation Hooks (hooks.py)`  [INFERRED]
  inventree_part_import/suppliers/base.py → README.md
- `Safety via Dry Run` --rationale_for--> `DryInvenTreeAPI`  [INFERRED]
  README.md → inventree_part_import/cli.py
- `TestCli` --uses--> `inventree_part_import`  [INFERRED]
  tests/test_cli.py → inventree_part_import/cli.py
- `setup_categories_and_parameters` --uses--> `InvenTreeObjectCreationError`  [INFERRED]
  inventree_part_import/categories.py → inventree_part_import/exceptions.py
- `PartImporter` --uses--> `InvenTreeObjectCreationError`  [INFERRED]
  inventree_part_import/part_importer.py → inventree_part_import/exceptions.py

## Hyperedges (group relationships)
- **Supplier Implementations** — suppliers_digikey_DigiKey, suppliers_lcsc_LCSC, suppliers_mouser_Mouser, suppliers_reichelt_Reichelt, suppliers_tme_TME [EXTRACTED 1.00]

## Communities

### Community 0 - "InvenTree API Integration"
Cohesion: 0.23
Nodes (4): _download_file_content(), upload_datasheet(), upload_image(), url2filename()

### Community 1 - "Supplier Base & Hooks"
Cohesion: 0.42
Nodes (10): SupplierError, SupplierLoadError, Pre Creation Hooks (hooks.py), ApiPart, Supplier, DigiKey, LCSC, Mouser (+2 more)

### Community 2 - "Custom Exceptions"
Cohesion: 0.28
Nodes (5): Exception, InvenTreeObjectCreationError, InvenTreePartImportError, Company, create_manufacturer()

### Community 3 - "CLI & Core Logic"
Cohesion: 0.33
Nodes (7): setup_categories_and_parameters, DryInvenTreeAPI, inventree_part_import, setup_inventree_api, PartImporter, Safety via Dry Run, RetryInvenTreeAPI

### Community 4 - "CLI Integration Tests"
Cohesion: 0.4
Nodes (1): TestCli

### Community 5 - "Localization Support"
Cohesion: 0.67
Nodes (0): 

### Community 6 - "Package Initialization"
Cohesion: 1.0
Nodes (0): 

### Community 7 - "Main Entrypoint"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **3 isolated node(s):** `RetryInvenTreeAPI`, `Pre Creation Hooks (hooks.py)`, `Safety via Dry Run`
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Package Initialization`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Main Entrypoint`** (1 nodes): `__main__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `InvenTreeObjectCreationError` connect `Custom Exceptions` to `CLI & Core Logic`?**
  _High betweenness centrality (0.242) - this node is a cross-community bridge._
- **Why does `PartImporter` connect `CLI & Core Logic` to `Supplier Base & Hooks`, `Custom Exceptions`?**
  _High betweenness centrality (0.236) - this node is a cross-community bridge._
- **Why does `inventree_part_import` connect `CLI & Core Logic` to `CLI Integration Tests`?**
  _High betweenness centrality (0.183) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `ApiPart` (e.g. with `Pre Creation Hooks (hooks.py)` and `PartImporter`) actually correct?**
  _`ApiPart` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `InvenTreeObjectCreationError` (e.g. with `PartImporter` and `setup_categories_and_parameters`) actually correct?**
  _`InvenTreeObjectCreationError` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `SupplierError` (e.g. with `LCSC` and `TME`) actually correct?**
  _`SupplierError` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Supplier` (e.g. with `SupplierError` and `SupplierLoadError`) actually correct?**
  _`Supplier` has 3 INFERRED edges - model-reasoned connections that need verification._