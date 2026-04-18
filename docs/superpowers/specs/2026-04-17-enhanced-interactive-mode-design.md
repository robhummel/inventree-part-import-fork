# Enhanced Interactive Mode: `twice-add`

**Date:** 2026-04-17
**Status:** Approved

## Overview

Add a new `--interactive twice-add` mode that extends the existing `twice` mode with the ability to interactively create missing InvenTree part categories and their parameter templates during import, driven by DigiKey supplier data. Configuration files (`categories.yaml`, `parameters.yaml`) are updated live so subsequent imports in the same session benefit immediately.

## Scope & Constraints

- Category creation is DigiKey-only (other suppliers lack reliable structured category/parameter data).
- The feature is gated behind `twice-add`; existing `true` / `twice` / `false` behavior is unchanged.
- All config writes use the existing `update_config_file` context manager pattern.

---

## Section 1: CLI & Mode Gating

### Change

`InteractiveChoices` in `cli.py` gains a fifth value: `"twice-add"`.

```python
InteractiveChoices = click.Choice(
    ("default", "false", "true", "twice", "twice-add"), case_sensitive=False
)
```

The help string for `--interactive` is updated to describe `twice-add`:

> `'twice-add'` behaves like `'twice'` but also allows creating missing categories and parameters from DigiKey data during the interactive pass.

### PartImporter construction

`PartImporter.__init__` gains a new keyword argument:

```python
def __init__(
    self,
    inventree_api: InvenTreeAPI,
    interactive: bool = False,
    allow_category_creation: bool = False,
    verbose: bool = False,
):
```

In `cli.py`, the importer is constructed as:

```python
importer = PartImporter(
    inventree_api,
    interactive=interactive == "true",
    allow_category_creation=interactive == "twice-add",
    verbose=verbose,
)
```

On the second (`twice-add`) pass, both `importer.interactive` and `importer.allow_category_creation` are `True`.

---

## Section 2: Category Creation Flow

### `CategoryCreator` class (`categories.py`)

A new class responsible for the full create-category interactive flow. `PartImporter` holds an optional instance:

```python
self.category_creator: CategoryCreator | None = (
    CategoryCreator(inventree_api, self.category_map, self.parameter_map, self.parameter_templates)
    if allow_category_creation
    else None
)
```

`CategoryCreator` is always instantiated when `allow_category_creation=True`. The DigiKey gate is applied in `import_supplier_part` by checking `supplier.name == "DigiKey"` (where `supplier` is the InvenTree `Company` object). `create_manufacturer_part` gains an optional parameter:

```python
def create_manufacturer_part(
    self,
    api_part: ApiPart,
    part: Part | None = None,
    category_creator: CategoryCreator | None = None,
):
```

In `import_supplier_part`, the call becomes:

```python
result = self.create_manufacturer_part(
    api_part,
    part,
    category_creator=self.category_creator if supplier.name == "DigiKey" else None,
)
```

### Trigger point

In `PartImporter.create_manufacturer_part` (currently line 259–273), after the existing category fuzzy-match loop fails:

```python
else:
    path_str = f" {BOLD}/{BOLD_END} ".join(api_part.category_path)
    if not self.interactive:
        error(f"failed to match category for '{path_str}'")
        return ImportResult.FAILURE

    prompt(f"failed to match category for '{path_str}', select category")
    # NEW: append "Create New Category..." to the selection choices
    if not (category := self.select_category(api_part.category_path, self.category_creator)):
        return ImportResult.FAILURE
```

`select_category` gains an optional `category_creator` parameter. When it is set, a `"Create New Category..."` option is appended to the choice list. Selecting it delegates to `category_creator.create_from_api_part(api_part)`.

### Category path editing sub-flow (`CategoryCreator.create_from_api_part`)

1. Display DigiKey's `category_path` (e.g. `["Semiconductors", "Transistors", "BJT"]`) as a numbered list with the full joined path shown.
2. Present three options:
   - **Confirm as-is**
   - **Truncate** — prompt for how many trailing segments to drop (e.g. drop 1 → `["Semiconductors", "Transistors"]`)
   - **Rename** — prompt for a new name for each segment in turn (blank = keep original)
3. The confirmed path is created in InvenTree: for each segment not already present, `PartCategory.create()` is called with the correct `parent` pk.
4. A `CategoryStub` is built from the confirmed path and written to `categories.yaml` as a nested dict under the appropriate root, including the `_parameters` list populated in Section 3.
5. A `Category` object (with `part_category` set) is returned to `create_manufacturer_part`, which then proceeds to `Part.create()` as normal.
6. The new category is inserted into `PartImporter.category_map` and `self.categories` so subsequent parts in the same session can match it without re-prompting.

---

## Section 3: Parameter Selection & Config Writing

### Multi-select list

After path confirmation, `CategoryCreator` presents a `select_multiple` list (using `cutie`) of all DigiKey parameters for the part, formatted as:

```
100nF | Capacitance
X7R   | Dielectric
50V   | Rated Voltage
...
```

Items are pre-ticked where the DigiKey parameter name fuzzy-matches (via `thefuzz.fuzz.partial_ratio` ≥ 80) an existing entry in `parameters.yaml` (matched against parameter names and aliases). The threshold of 80 is the same used elsewhere in the codebase.

### Per-parameter handling

For each selected parameter:

| Scenario | Action |
|---|---|
| Name matches existing `parameters.yaml` entry | Added to `_parameters` list for the new category; no prompt |
| Name is new | Prompt: `units for '{name}' (leave blank if none)` → add to `parameters.yaml` with that unit; add to `_parameters` list |

New parameters are added to `parameters.yaml` using `update_config_file(PARAMETERS_CONFIG)`.

### In-memory updates

After writing:
- New parameters are added to `PartImporter.parameter_map` so they match immediately for the current part's `setup_parameters` call.
- New `ParameterTemplate` objects are created in InvenTree (via `ParameterTemplate.create`) for any parameters that didn't previously exist, and added to `PartImporter.parameter_templates`.

---

## Data Flow Summary

```
twice-add second pass
  └─ import_part(part)
       └─ import_supplier_part(DigiKey, api_part)
            └─ create_manufacturer_part(api_part)
                 └─ [no category match]
                      └─ select_category(..., category_creator)
                           └─ [user picks "Create New Category..."]
                                └─ CategoryCreator.create_from_api_part(api_part)
                                     ├─ path editing sub-flow → PartCategory.create() x N
                                     ├─ parameter multi-select
                                     ├─ units prompt for new params → ParameterTemplate.create()
                                     ├─ write categories.yaml + parameters.yaml
                                     └─ return Category
                      └─ Part.create(category=new_category)
```

---

## Error Handling

- If `PartCategory.create()` fails for any segment, raise `InvenTreeObjectCreationError` (existing pattern).
- If the user selects zero parameters, the category is created with an empty `_parameters` list — valid and recoverable later.
- If the user skips at the "Create New Category..." step, fall through to `ImportResult.FAILURE` as today.
- Config writes use the existing backup-then-write pattern in `update_config_file`.

---

## Testing

- Unit test: `CategoryCreator.create_from_api_part` with mocked InvenTree API and a fixture DigiKey `ApiPart` — verify correct `categories.yaml` and `parameters.yaml` output for path truncation, rename, and parameter selection scenarios.
- Integration test (existing docker-compose setup): run `twice-add` against a live InvenTree instance with a DigiKey part whose category doesn't exist; assert the category and parameters appear in InvenTree and in the config files.
- Regression: existing `true` / `twice` behavior unchanged — no `CategoryCreator` instance created, `select_category` unchanged when `category_creator=None`.
