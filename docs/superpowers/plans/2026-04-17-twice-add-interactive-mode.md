# Enhanced Interactive Mode (`twice-add`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--interactive twice-add` mode that lets users interactively create missing InvenTree part categories and parameter templates from DigiKey data during import, with live `categories.yaml` / `parameters.yaml` updates.

**Architecture:** A `CategoryCreator` class is added to `categories.py` (which already owns all category config logic). `PartImporter` holds an optional instance and passes it through `select_category` → `create_manufacturer_part`. The DigiKey guard lives in `import_supplier_part` via `supplier.name == "DigiKey"`.

**Tech Stack:** Python 3.11+, click (CLI), cutie (interactive prompts), thefuzz (fuzzy matching), pyyaml (config writes), inventree SDK (PartCategory/ParameterTemplate creation), pytest + unittest.mock (tests).

---

## File Map

| File | Change |
|---|---|
| `inventree_part_import/cli.py` | Add `"twice-add"` choice, update help, pass `allow_category_creation` to `PartImporter`, set it `True` on second pass |
| `inventree_part_import/part_importer.py` | Add `allow_category_creation` param + `category_creator` attr; extend `select_category`, `create_manufacturer_part`, `import_supplier_part` |
| `inventree_part_import/categories.py` | Add `CategoryCreator` class |
| `tests/test_category_creator.py` | New: unit tests for `CategoryCreator` |

---

## Task 1: Add `twice-add` CLI option

**Files:**
- Modify: `inventree_part_import/cli.py:62` (`InteractiveChoices`)
- Modify: `inventree_part_import/cli.py:71-79` (`--interactive` option)
- Modify: `inventree_part_import/cli.py:230` (`PartImporter` construction)
- Modify: `inventree_part_import/cli.py:261-279` (second pass block)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_category_creator.py
from click.testing import CliRunner
from inventree_part_import.cli import inventree_part_import

def test_twice_add_is_valid_interactive_choice():
    result = CliRunner().invoke(inventree_part_import, ["--interactive", "twice-add", "--help"])
    assert result.exit_code == 0
    assert "twice-add" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/Rob/OSS/inventree-part-import-fork
uv run pytest tests/test_category_creator.py::test_twice_add_is_valid_interactive_choice -v
```

Expected: FAIL — `Invalid value for '-i' / '--interactive': 'twice-add' is not one of ...`

- [ ] **Step 3: Update `InteractiveChoices` and help text in `cli.py`**

Replace the existing `InteractiveChoices` line (line 62) with:

```python
InteractiveChoices = click.Choice(("default", "false", "true", "twice", "twice-add"), case_sensitive=False)
```

Update the `--interactive` help string (lines 75-79):

```python
help=(
    "Enable interactive mode. 'twice' will run once normally, then rerun in interactive "
    "mode for any parts that failed to import correctly. 'twice-add' behaves like 'twice' "
    "but also allows creating missing categories and parameters from DigiKey data."
),
```

Update the `PartImporter` construction (line 230):

```python
importer = PartImporter(
    inventree_api,
    interactive=interactive == "true",
    allow_category_creation=interactive == "twice-add",
    verbose=verbose,
)
```

Update the second pass condition (line 261) to include `"twice-add"`:

```python
if parts2 and interactive in {"twice", "twice-add"} and last_import_result != ImportResult.ERROR:
    success("reimporting failed/incomplete parts in interactive mode ...\n", prefix="")
    failed_parts = []
    incomplete_parts = []

    importer.interactive = True
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_category_creator.py::test_twice_add_is_valid_interactive_choice -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add inventree_part_import/cli.py tests/test_category_creator.py
git commit -m "feat: add twice-add to interactive mode choices"
```

---

## Task 2: Add `allow_category_creation` plumbing to `PartImporter`

**Files:**
- Modify: `inventree_part_import/part_importer.py:46-65` (`PartImporter.__init__`)
- Modify: `inventree_part_import/part_importer.py:170` (`import_supplier_part` signature)
- Modify: `inventree_part_import/part_importer.py:186-191` (`create_manufacturer_part` call in `import_supplier_part`)
- Modify: `inventree_part_import/part_importer.py:250` (`create_manufacturer_part` signature)
- Modify: `inventree_part_import/part_importer.py:295` (`select_category` signature)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_category_creator.py  (append)
from unittest.mock import MagicMock, patch
from inventree_part_import.part_importer import PartImporter

def test_part_importer_stores_allow_category_creation():
    api = MagicMock()
    api.api_version = 999

    with patch("inventree_part_import.part_importer.setup_categories_and_parameters", return_value=({}, {})), \
         patch("inventree_part_import.part_importer.get_parameter_templates", return_value={}), \
         patch("inventree_part_import.part_importer.get_pre_creation_hooks"):
        importer = PartImporter(api, allow_category_creation=True)

    assert importer.allow_category_creation is True
    assert importer.category_creator is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_category_creator.py::test_part_importer_stores_allow_category_creation -v
```

Expected: FAIL — `PartImporter.__init__() got an unexpected keyword argument 'allow_category_creation'`

- [ ] **Step 3: Update `PartImporter.__init__`**

Replace the `__init__` signature and body (lines 47-64 of `part_importer.py`):

```python
def __init__(
    self,
    inventree_api: InvenTreeAPI,
    interactive: bool = False,
    allow_category_creation: bool = False,
    verbose: bool = False,
):
    self.api = inventree_api
    self.interactive = interactive
    self.allow_category_creation = allow_category_creation
    self.verbose = verbose

    # preload pre_creation_hooks
    get_pre_creation_hooks()

    self.category_map, self.parameter_map = setup_categories_and_parameters(self.api)
    self.parameter_templates = get_parameter_templates(self.api)

    self.part_category_to_category: dict[int, Category] = {
        cast(int, category.part_category.pk): category
        for category in self.category_map.values()
    }
    self.categories = set(self.category_map.values())

    self.category_creator: CategoryCreator | None = (
        CategoryCreator(
            inventree_api,
            self.category_map,
            self.parameter_map,
            self.parameter_templates,
        )
        if allow_category_creation
        else None
    )
```

Add the import at the top of `part_importer.py` (alongside the existing `.categories` import):

```python
from .categories import Category, CategoryCreator, setup_categories_and_parameters
```

- [ ] **Step 4: Update `select_category` signature**

Replace line 295:

```python
def select_category(self, category_path: list[str]):
```

with:

```python
def select_category(
    self,
    category_path: list[str],
    api_part: ApiPart | None = None,
    category_creator: CategoryCreator | None = None,
) -> Category | None:
```

Add `ApiPart` to the imports at the top:

```python
from .suppliers.base import ApiPart
```

- [ ] **Step 5: Update `create_manufacturer_part` signature**

Replace line 250:

```python
def create_manufacturer_part(
    self,
    api_part: ApiPart,
    part: Part | None = None,
):
```

with:

```python
def create_manufacturer_part(
    self,
    api_part: ApiPart,
    part: Part | None = None,
    category_creator: CategoryCreator | None = None,
) -> tuple[ManufacturerPart, Part] | ImportResult:
```

Update the call to `select_category` inside `create_manufacturer_part` (around line 269):

```python
prompt(f"failed to match category for '{path_str}', select category")
if not (category := self.select_category(
    api_part.category_path,
    api_part=api_part,
    category_creator=category_creator,
)):
    return ImportResult.FAILURE
```

- [ ] **Step 6: Update `import_supplier_part` to pass `category_creator`**

Replace the `self.create_manufacturer_part(api_part, part)` call (around line 187) with:

```python
result = self.create_manufacturer_part(
    api_part,
    part,
    category_creator=self.category_creator if supplier.name == "DigiKey" else None,
)
```

- [ ] **Step 7: Run test to verify it passes**

```bash
uv run pytest tests/test_category_creator.py::test_part_importer_stores_allow_category_creation -v
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add inventree_part_import/part_importer.py
git commit -m "feat: add allow_category_creation plumbing to PartImporter"
```

---

## Task 3: Add `CategoryCreator` class skeleton + path editing

**Files:**
- Modify: `inventree_part_import/categories.py` (add class + `_edit_path`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_category_creator.py  (append)
from unittest.mock import MagicMock, patch
from inventree_part_import.categories import CategoryCreator, Category, Parameter

def _make_creator(category_map=None, parameter_map=None, parameter_templates=None):
    api = MagicMock()
    return CategoryCreator(
        api,
        category_map if category_map is not None else {},
        parameter_map if parameter_map is not None else {},
        parameter_templates if parameter_templates is not None else {},
    )

@patch("inventree_part_import.categories.select", return_value=0)
def test_edit_path_confirm(mock_select):
    creator = _make_creator()
    result = creator._edit_path(["Semiconductors", "Transistors", "BJT"])
    assert result == ["Semiconductors", "Transistors", "BJT"]

@patch("inventree_part_import.categories.prompt_input", return_value="1")
@patch("inventree_part_import.categories.select", return_value=1)
def test_edit_path_truncate_by_one(mock_select, mock_input):
    creator = _make_creator()
    result = creator._edit_path(["Semiconductors", "Transistors", "BJT"])
    assert result == ["Semiconductors", "Transistors"]

@patch("inventree_part_import.categories.prompt_input", side_effect=["", "FETs", ""])
@patch("inventree_part_import.categories.select", return_value=2)
def test_edit_path_rename_middle_segment(mock_select, mock_input):
    creator = _make_creator()
    result = creator._edit_path(["Semiconductors", "Transistors", "BJT"])
    assert result == ["Semiconductors", "FETs", "BJT"]

@patch("inventree_part_import.categories.select", return_value=3)
def test_edit_path_skip_returns_none(mock_select):
    creator = _make_creator()
    result = creator._edit_path(["Semiconductors", "Transistors"])
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_category_creator.py -k "edit_path" -v
```

Expected: FAIL — `cannot import name 'CategoryCreator' from 'inventree_part_import.categories'`

- [ ] **Step 3: Add required imports to `categories.py`**

Add to the top of `categories.py`:

```python
from __future__ import annotations
```

Add to the existing imports block (keep existing imports, add the new ones):

```python
from typing import TYPE_CHECKING, Any, cast  # add TYPE_CHECKING if not present

from cutie import prompt_input, prompt_yes_or_no, select, select_multiple  # extend existing cutie import
from error_helper import BOLD, BOLD_END, hint, info, prompt, success, warning  # extend existing

from thefuzz import fuzz  # new import
```

Add at the end of the imports block:

```python
if TYPE_CHECKING:
    from .suppliers.base import ApiPart
```

- [ ] **Step 4: Add `CategoryCreator` class with `_edit_path` to `categories.py`**

Append at the end of `categories.py`:

```python
class CategoryCreator:
    def __init__(
        self,
        inventree_api: InvenTreeAPI,
        category_map: dict[str, Category],
        parameter_map: dict[str, list[Parameter]],
        parameter_templates: dict[str, ParameterTemplate],
    ):
        self.api = inventree_api
        self.category_map = category_map
        self.parameter_map = parameter_map
        self.parameter_templates = parameter_templates

    def create_from_api_part(self, api_part: ApiPart) -> Category | None:
        confirmed_path = self._edit_path(api_part.category_path)
        if confirmed_path is None:
            return None

        part_category = self._create_inventree_categories(confirmed_path)
        if part_category is None:
            return None

        selected_param_names, new_param_units = self._select_parameters(api_part.parameters)
        self._write_configs(confirmed_path, selected_param_names, new_param_units)
        self._create_parameter_templates(new_param_units)

        category_stub = CategoryStub(
            name=confirmed_path[-1],
            path=confirmed_path,
            description=confirmed_path[-1],
            ignore=False,
            structural=False,
            aliases=[],
            parameters=selected_param_names,
        )
        category = Category.from_stub(category_stub, part_category)
        self._update_maps(category, new_param_units)
        return category

    def _edit_path(self, category_path: list[str]) -> list[str] | None:
        info(f"DigiKey category path: {' / '.join(category_path)}", end="\n")
        prompt("select action for category path")
        choices = [
            "Confirm as-is",
            "Truncate (drop trailing segments)",
            "Rename segments",
            f"{BOLD}Skip ...{BOLD_END}",
        ]
        index = select(choices, deselected_prefix="  ", selected_prefix="> ")
        if index == 3:
            return None
        if index == 0:
            return list(category_path)
        if index == 1:
            raw = prompt_input(f"segments to drop (1-{len(category_path) - 1})")
            n = max(1, min(int(raw or "1"), len(category_path) - 1))
            return list(category_path[:-n])
        # index == 2: rename
        renamed = []
        for segment in category_path:
            new_name = prompt_input(f"name for '{segment}' (blank to keep)") or segment
            renamed.append(new_name)
        return renamed

    def _create_inventree_categories(self, path: list[str]) -> PartCategory | None:
        raise NotImplementedError

    def _select_parameters(
        self, api_parameters: dict[str, str]
    ) -> tuple[list[str], dict[str, str]]:
        raise NotImplementedError

    def _write_configs(
        self, path: list[str], param_names: list[str], new_param_units: dict[str, str]
    ) -> None:
        raise NotImplementedError

    def _create_parameter_templates(self, new_param_units: dict[str, str]) -> None:
        raise NotImplementedError

    def _update_maps(self, category: Category, new_param_units: dict[str, str]) -> None:
        raise NotImplementedError
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_category_creator.py -k "edit_path" -v
```

Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add inventree_part_import/categories.py tests/test_category_creator.py
git commit -m "feat: add CategoryCreator skeleton with path editing"
```

---

## Task 4: Implement `_create_inventree_categories`

**Files:**
- Modify: `inventree_part_import/categories.py` (`CategoryCreator._create_inventree_categories`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_category_creator.py  (append)
from unittest.mock import MagicMock, patch, call

@patch("inventree_part_import.categories.PartCategory.list", return_value=[])
@patch("inventree_part_import.categories.PartCategory.create")
def test_create_inventree_categories_all_new(mock_create, mock_list):
    parent = MagicMock(pk=1, parent=None)
    child = MagicMock(pk=2, parent=1)
    leaf = MagicMock(pk=3, parent=2)
    mock_create.side_effect = [parent, child, leaf]

    creator = _make_creator()
    result = creator._create_inventree_categories(["A", "B", "C"])

    assert result is leaf
    assert mock_create.call_count == 3
    mock_create.assert_any_call(
        creator.api, {"name": "A", "description": "A", "structural": False, "parent": None}
    )
    mock_create.assert_any_call(
        creator.api, {"name": "B", "description": "B", "structural": False, "parent": 1}
    )
    mock_create.assert_any_call(
        creator.api, {"name": "C", "description": "C", "structural": False, "parent": 2}
    )

@patch("inventree_part_import.categories.PartCategory.list")
@patch("inventree_part_import.categories.PartCategory.create")
def test_create_inventree_categories_skips_existing(mock_create, mock_list):
    existing_root = MagicMock(pk=10, parent=None, name="A")
    mock_list.return_value = [existing_root]
    leaf = MagicMock(pk=11, parent=10)
    mock_create.return_value = leaf

    creator = _make_creator()
    result = creator._create_inventree_categories(["A", "B"])

    assert result is leaf
    assert mock_create.call_count == 1
    mock_create.assert_called_once_with(
        creator.api, {"name": "B", "description": "B", "structural": False, "parent": 10}
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_category_creator.py -k "create_inventree" -v
```

Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `_create_inventree_categories`**

Replace the `raise NotImplementedError` stub in `CategoryCreator._create_inventree_categories`:

```python
def _create_inventree_categories(self, path: list[str]) -> PartCategory | None:
    by_pk: dict[Any, PartCategory] = {cat.pk: cat for cat in PartCategory.list(self.api)}
    existing: dict[tuple[str, ...], PartCategory] = {}
    for cat in by_pk.values():
        segments: list[str] = [cat.name]
        parent = cat
        while parent := by_pk.get(parent.parent):
            segments.insert(0, parent.name)
        existing[tuple(segments)] = cat

    parent_pk: int | None = None
    part_category: PartCategory | None = None
    for i in range(1, len(path) + 1):
        segment_path = tuple(path[:i])
        if cat := existing.get(segment_path):
            parent_pk = cast(int, cat.pk)
            part_category = cat
            continue
        info(f"creating category '{'/'.join(segment_path)}' ...")
        part_category = PartCategory.create(
            self.api,
            {
                "name": path[i - 1],
                "description": path[i - 1],
                "structural": False,
                "parent": parent_pk,
            },
        )
        if part_category is None:
            raise InvenTreeObjectCreationError(PartCategory)
        parent_pk = cast(int, part_category.pk)

    return part_category
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_category_creator.py -k "create_inventree" -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add inventree_part_import/categories.py tests/test_category_creator.py
git commit -m "feat: implement CategoryCreator._create_inventree_categories"
```

---

## Task 5: Implement `_select_parameters`

**Files:**
- Modify: `inventree_part_import/categories.py` (`CategoryCreator._select_parameters`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_category_creator.py  (append)

@patch("inventree_part_import.categories.prompt_input", return_value="V")
@patch("inventree_part_import.categories.select_multiple", return_value=[0, 1])
def test_select_parameters_pre_ticks_existing_and_prompts_units_for_new(
    mock_select_multiple, mock_input
):
    # "Capacitance" matches existing parameter_map entry; "NewParam" does not
    parameter_map = {"capacitance": [Parameter("Capacitance", "Capacitance", [], "F")]}
    creator = _make_creator(parameter_map=parameter_map)

    names, new_units = creator._select_parameters({"Capacitance": "100nF", "NewParam": "42"})

    assert names == ["Capacitance", "NewParam"]
    assert "NewParam" in new_units
    assert new_units["NewParam"] == "V"
    assert "Capacitance" not in new_units  # existing — no units prompt

    call_kwargs = mock_select_multiple.call_args[1]
    ticked = call_kwargs.get("ticked_indices", [])
    assert 0 in ticked   # Capacitance pre-ticked
    assert 1 not in ticked  # NewParam not pre-ticked

@patch("inventree_part_import.categories.prompt_input", return_value="")
@patch("inventree_part_import.categories.select_multiple", return_value=[])
def test_select_parameters_empty_selection(mock_select_multiple, mock_input):
    creator = _make_creator()
    names, new_units = creator._select_parameters({"Voltage": "50V"})
    assert names == []
    assert new_units == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_category_creator.py -k "select_parameters" -v
```

Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `_select_parameters`**

Replace the `raise NotImplementedError` stub:

```python
def _select_parameters(
    self, api_parameters: dict[str, str]
) -> tuple[list[str], dict[str, str]]:
    param_names = list(api_parameters.keys())
    param_values = list(api_parameters.values())

    max_val_len = max((len(v) for v in param_values), default=0)
    choices = [
        f"{v.ljust(max_val_len)} | {n}"
        for n, v in zip(param_names, param_values)
    ]

    ticked = [
        i
        for i, name in enumerate(param_names)
        if any(fuzz.partial_ratio(name.lower(), key) >= 80 for key in self.parameter_map)
    ]

    prompt(
        "select parameters to add to this category "
        "(SPACEBAR to toggle, ENTER to confirm)",
        end="\n",
    )
    selected_indices = select_multiple(
        choices,
        ticked_indices=ticked,
        deselected_unticked_prefix="  [ ] ",
        deselected_ticked_prefix="  [x] ",
        selected_unticked_prefix="> [ ] ",
        selected_ticked_prefix="> [x] ",
    )

    selected_names = [param_names[i] for i in selected_indices]

    new_param_units: dict[str, str] = {}
    for name in selected_names:
        if not any(fuzz.partial_ratio(name.lower(), key) >= 80 for key in self.parameter_map):
            units = prompt_input(f"units for '{name}' (blank if none)") or ""
            new_param_units[name] = units

    return selected_names, new_param_units
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_category_creator.py -k "select_parameters" -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add inventree_part_import/categories.py tests/test_category_creator.py
git commit -m "feat: implement CategoryCreator._select_parameters with pre-ticking"
```

---

## Task 6: Implement config writes, ParameterTemplate creation, and in-memory map updates

**Files:**
- Modify: `inventree_part_import/categories.py` (`_write_configs`, `_create_parameter_templates`, `_update_maps`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_category_creator.py  (append)
import yaml
import tempfile
from pathlib import Path
from inventree_part_import.config import set_config_dir, CATEGORIES_CONFIG, PARAMETERS_CONFIG

def _setup_temp_config(tmp_path: Path):
    set_config_dir(tmp_path)
    (tmp_path / CATEGORIES_CONFIG).write_text("Electronics:\n", encoding="utf-8")
    (tmp_path / PARAMETERS_CONFIG).write_text("Capacitance:\n", encoding="utf-8")

def test_write_configs_adds_category_and_new_parameter(tmp_path):
    _setup_temp_config(tmp_path)
    creator = _make_creator()

    creator._write_configs(
        path=["Electronics", "Capacitors"],
        param_names=["Capacitance", "Voltage"],
        new_param_units={"Voltage": "V"},
    )

    cats = yaml.safe_load((tmp_path / CATEGORIES_CONFIG).read_text())
    assert "Capacitors" in cats["Electronics"]
    assert cats["Electronics"]["Capacitors"]["_parameters"] == ["Capacitance", "Voltage"]

    params = yaml.safe_load((tmp_path / PARAMETERS_CONFIG).read_text())
    assert "Voltage" in params
    assert params["Voltage"]["_unit"] == "V"

def test_write_configs_empty_params(tmp_path):
    _setup_temp_config(tmp_path)
    creator = _make_creator()

    creator._write_configs(path=["NewCategory"], param_names=[], new_param_units={})

    cats = yaml.safe_load((tmp_path / CATEGORIES_CONFIG).read_text())
    assert "NewCategory" in cats

@patch("inventree_part_import.categories.ParameterTemplate.create")
def test_create_parameter_templates(mock_create):
    mock_template = MagicMock()
    mock_create.return_value = mock_template
    templates: dict[str, Any] = {}
    creator = _make_creator(parameter_templates=templates)

    creator._create_parameter_templates({"Voltage": "V", "Current": ""})

    assert mock_create.call_count == 2
    mock_create.assert_any_call(
        creator.api, {"name": "Voltage", "description": "Voltage", "units": "V"}
    )
    mock_create.assert_any_call(
        creator.api, {"name": "Current", "description": "Current", "units": ""}
    )
    assert "Voltage" in templates
    assert "Current" in templates

def test_update_maps_adds_category_and_parameters():
    from inventree_part_import.categories import CategoryStub
    category_map: dict[str, Any] = {}
    parameter_map: dict[str, list[Parameter]] = {}
    creator = _make_creator(category_map=category_map, parameter_map=parameter_map)

    stub = CategoryStub(
        name="BJT",
        path=["Semiconductors", "BJT"],
        description="BJT",
        ignore=False,
        structural=False,
        aliases=[],
        parameters=["Voltage"],
    )
    part_cat = MagicMock(pk=99)
    category = Category.from_stub(stub, part_cat)

    creator._update_maps(category, {"Voltage": "V"})

    assert "bjt" in category_map
    assert "voltage" in parameter_map
    assert parameter_map["voltage"][0].name == "Voltage"
    assert parameter_map["voltage"][0].units == "V"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_category_creator.py -k "write_configs or create_parameter or update_maps" -v
```

Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `_write_configs`**

Replace the `raise NotImplementedError` stub:

```python
def _write_configs(
    self, path: list[str], param_names: list[str], new_param_units: dict[str, str]
) -> None:
    with update_config_file(CATEGORIES_CONFIG) as categories_config:
        node: dict[str, Any] = categories_config
        for segment in path[:-1]:
            if node.get(segment) is None:
                node[segment] = {}
            node = node[segment]
        leaf: dict[str, Any] = {}
        if param_names:
            leaf["_parameters"] = param_names
        node[path[-1]] = leaf if leaf else None

    if new_param_units:
        with update_config_file(PARAMETERS_CONFIG) as parameters_config:
            for name, units in new_param_units.items():
                entry: dict[str, Any] = {}
                if units:
                    entry["_unit"] = units
                parameters_config[name] = entry if entry else None
```

- [ ] **Step 4: Implement `_create_parameter_templates`**

Replace the `raise NotImplementedError` stub:

```python
def _create_parameter_templates(self, new_param_units: dict[str, str]) -> None:
    for name, units in new_param_units.items():
        info(f"creating parameter template '{name}' ...")
        template = ParameterTemplate.create(
            self.api,
            {"name": name, "description": name, "units": units},
        )
        if template is None:
            raise InvenTreeObjectCreationError(ParameterTemplate)
        self.parameter_templates[name] = template

def _link_parameters_to_category(
    self, part_category: PartCategory, selected_param_names: list[str]
) -> None:
    for name in selected_param_names:
        if template := self.parameter_templates.get(name):
            info(f"linking parameter '{name}' to '{part_category.pathstring}' ...")
            link = PartCategoryParameterTemplate.create(
                self.api,
                {"category": part_category.pk, "template": template.pk},
            )
            if link is None:
                raise InvenTreeObjectCreationError(PartCategoryParameterTemplate)
```

Add the call to `_link_parameters_to_category` inside `create_from_api_part`, after `_create_parameter_templates`:

```python
def create_from_api_part(self, api_part: ApiPart) -> Category | None:
    confirmed_path = self._edit_path(api_part.category_path)
    if confirmed_path is None:
        return None

    part_category = self._create_inventree_categories(confirmed_path)
    if part_category is None:
        return None

    selected_param_names, new_param_units = self._select_parameters(api_part.parameters)
    self._write_configs(confirmed_path, selected_param_names, new_param_units)
    self._create_parameter_templates(new_param_units)
    self._link_parameters_to_category(part_category, selected_param_names)  # NEW

    category_stub = CategoryStub(
        name=confirmed_path[-1],
        path=confirmed_path,
        description=confirmed_path[-1],
        ignore=False,
        structural=False,
        aliases=[],
        parameters=selected_param_names,
    )
    category = Category.from_stub(category_stub, part_category)
    self._update_maps(category, new_param_units)
    return category
```
```

- [ ] **Step 5: Implement `_update_maps`**

Replace the `raise NotImplementedError` stub:

```python
def _update_maps(self, category: Category, new_param_units: dict[str, str]) -> None:
    for alias in (*category.aliases, category.name):
        self.category_map[alias.lower()] = category

    for name, units in new_param_units.items():
        parameter = Parameter(name=name, description=name, aliases=[], units=units)
        if existing := self.parameter_map.get(name.lower()):
            existing.append(parameter)
        else:
            self.parameter_map[name.lower()] = [parameter]
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_category_creator.py -k "write_configs or create_parameter or update_maps" -v
```

Expected: 4 PASS

- [ ] **Step 7: Commit**

```bash
git add inventree_part_import/categories.py tests/test_category_creator.py
git commit -m "feat: implement CategoryCreator config writes and in-memory updates"
```

---

## Task 7: Wire `select_category` to offer "Create New Category..."

**Files:**
- Modify: `inventree_part_import/part_importer.py` (`select_category` body)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_category_creator.py  (append)
from inventree_part_import.categories import CategoryCreator, Category, CategoryStub
from inventree_part_import.suppliers.base import ApiPart

def _make_api_part():
    return ApiPart(
        description="Test part",
        image_url=None,
        datasheet_url=None,
        supplier_link="https://digikey.com/test",
        SKU="TEST-ND",
        manufacturer="TestMfr",
        manufacturer_link="",
        MPN="TEST123",
        quantity_available=100,
        packaging="Tape & Reel",
        category_path=["Semiconductors", "Transistors", "BJT"],
        parameters={"Voltage": "50V"},
        price_breaks={1: 0.10},
        currency="USD",
    )

@patch("inventree_part_import.part_importer.select", return_value=0)  # pick "Create New Category..."
def test_select_category_delegates_to_category_creator(mock_select):
    api = MagicMock()
    api.api_version = 999

    with patch("inventree_part_import.part_importer.setup_categories_and_parameters", return_value=({}, {})), \
         patch("inventree_part_import.part_importer.get_parameter_templates", return_value={}), \
         patch("inventree_part_import.part_importer.get_pre_creation_hooks"):
        importer = PartImporter(api, allow_category_creation=True)

    mock_creator = MagicMock(spec=CategoryCreator)
    stub = CategoryStub("BJT", ["Semiconductors", "BJT"], "BJT", False, False, [], [])
    mock_created_cat = Category.from_stub(stub, MagicMock(pk=1))
    mock_creator.create_from_api_part.return_value = mock_created_cat

    api_part = _make_api_part()
    result = importer.select_category(
        api_part.category_path,
        api_part=api_part,
        category_creator=mock_creator,
    )

    mock_creator.create_from_api_part.assert_called_once_with(api_part)
    assert result is mock_created_cat
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_category_creator.py::test_select_category_delegates_to_category_creator -v
```

Expected: FAIL — `create_from_api_part` not called (existing `select_category` doesn't know about `category_creator`)

- [ ] **Step 3: Update `select_category` body in `part_importer.py`**

Replace the full `select_category` method body (keeping the signature from Task 2):

```python
def select_category(
    self,
    category_path: list[str],
    api_part: ApiPart | None = None,
    category_creator: CategoryCreator | None = None,
) -> Category | None:
    search_terms = [category_path[-1], " ".join(category_path[-2:])]

    def rate_category(category: Category):
        return max(
            fuzz.ratio(term, name)
            for name in (category.name, " ".join(category.path[-2:]))
            for term in search_terms
        )

    category_matches = sorted(self.categories, key=rate_category, reverse=True)

    max_matches = int(get_config().get("interactive_category_matches", 5))
    N_MATCHES = min(max_matches, len(category_matches))

    create_option = [f"{BOLD}Create New Category ...{BOLD_END}"] if category_creator else []
    choices = [
        *(" / ".join(category.path) for category in category_matches[:N_MATCHES]),
        f"{BOLD}Enter Manually ...{BOLD_END}",
        *create_option,
        f"{BOLD}Skip ...{BOLD_END}",
    ]
    MANUAL_INDEX = N_MATCHES
    CREATE_INDEX = N_MATCHES + 1 if category_creator else -1
    SKIP_INDEX = N_MATCHES + 1 + (1 if category_creator else 0)

    while True:
        index = select(choices, deselected_prefix="  ", selected_prefix="> ")
        if index == SKIP_INDEX:
            return None
        elif index == CREATE_INDEX and category_creator and api_part is not None:
            result = category_creator.create_from_api_part(api_part)
            if result is not None:
                self.categories.add(result)
                self.part_category_to_category[cast(int, result.part_category.pk)] = result
            return result
        elif index < N_MATCHES:
            return category_matches[index]

        # MANUAL_INDEX: enter by name
        name = prompt_input("category name")
        if (category := self.category_map.get(name.lower())) and category.name == name:
            return category
        warning(f"category '{name}' does not exist")
        prompt("select category")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_category_creator.py::test_select_category_delegates_to_category_creator -v
```

Expected: PASS

- [ ] **Step 5: Run the full unit test suite**

```bash
uv run pytest tests/test_category_creator.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add inventree_part_import/part_importer.py tests/test_category_creator.py
git commit -m "feat: wire select_category to CategoryCreator for twice-add mode"
```

---

## Task 8: Run full test suite and verify no regressions

- [ ] **Step 1: Run the existing CLI tests (requires InvenTree running)**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: All existing tests PASS. If InvenTree isn't running, skip with `-k "not TestCli"`.

- [ ] **Step 2: Run all tests**

```bash
uv run pytest -v
```

Expected: All PASS

- [ ] **Step 3: Run type checker**

```bash
uv run basedpyright inventree_part_import/
```

Expected: No new errors (fix any that appear before committing).

- [ ] **Step 4: Final commit**

```bash
git add -p  # stage any type-fix edits
git commit -m "fix: resolve type errors from twice-add implementation"
```

---

## Spec Coverage Checklist

| Spec requirement | Task |
|---|---|
| `"twice-add"` added to `InteractiveChoices` | Task 1 |
| Help text updated | Task 1 |
| `PartImporter` constructed with `allow_category_creation` | Task 1 |
| Second pass sets `importer.interactive = True` for `twice-add` | Task 1 |
| `allow_category_creation` param on `PartImporter.__init__` | Task 2 |
| `category_creator` attribute on `PartImporter` | Task 2 |
| `create_manufacturer_part` gains `category_creator` param | Task 2 |
| DigiKey gate via `supplier.name == "DigiKey"` | Task 2 |
| `CategoryCreator` class in `categories.py` | Task 3 |
| Path editing: confirm, truncate, rename, skip | Task 3 |
| `PartCategory.create()` for missing segments | Task 4 |
| Skips already-existing parent segments | Task 4 |
| Multi-select with value display | Task 5 |
| Pre-ticking via fuzzy match ≥ 80 | Task 5 |
| Units prompt for new parameters | Task 5 |
| Write new category to `categories.yaml` | Task 6 |
| Write new parameters to `parameters.yaml` | Task 6 |
| `ParameterTemplate.create()` for new parameters | Task 6 |
| In-memory `category_map` update | Task 6 |
| In-memory `parameter_map` update | Task 6 |
| "Create New Category..." appended to `select_category` menu | Task 7 |
| Delegates to `category_creator.create_from_api_part` | Task 7 |
| `self.categories` updated after creation (for future fuzzy matching) | Task 7 |
| `self.part_category_to_category` updated (for `setup_parameters`) | Task 7 |
| `PartCategoryParameterTemplate` created to link params to category | Task 6 |
