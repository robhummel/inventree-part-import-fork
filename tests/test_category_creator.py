from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from inventree_part_import.cli import inventree_part_import
from inventree_part_import.part_importer import PartImporter


def test_twice_add_is_valid_interactive_choice():
    result = CliRunner().invoke(inventree_part_import, ["--interactive", "twice-add", "--help"])
    assert result.exit_code == 0
    assert "twice-add" in result.output
    assert "allows creating missing categories" in result.output
    assert "parameters from DigiKey data" in result.output

def test_part_importer_stores_allow_category_creation():
    api = MagicMock()
    api.api_version = 999

    with patch("inventree_part_import.part_importer.setup_categories_and_parameters", return_value=({}, {})), \
         patch("inventree_part_import.part_importer.get_parameter_templates", return_value={}), \
         patch("inventree_part_import.part_importer.get_pre_creation_hooks"):
        importer = PartImporter(api, allow_category_creation=True)

    assert importer.allow_category_creation is True
    assert importer.category_creator is not None

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
    existing_root = MagicMock(pk=10, parent=None)
    existing_root.name = "A"
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

import yaml
from pathlib import Path
from inventree_part_import.config import set_config_dir, CATEGORIES_CONFIG, PARAMETERS_CONFIG
from inventree_part_import.categories import CategoryStub

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
    assert cats["NewCategory"] is None

@patch("inventree_part_import.categories.ParameterTemplate.create")
def test_create_parameter_templates(mock_create):
    mock_template = MagicMock()
    mock_create.return_value = mock_template
    templates: dict = {}
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
    category_map: dict = {}
    parameter_map: dict = {}
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
