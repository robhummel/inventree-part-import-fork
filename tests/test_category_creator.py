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
