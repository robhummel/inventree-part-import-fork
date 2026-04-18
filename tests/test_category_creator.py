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
