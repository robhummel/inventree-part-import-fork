from click.testing import CliRunner
from inventree_part_import.cli import inventree_part_import


def test_twice_add_is_valid_interactive_choice():
    result = CliRunner().invoke(inventree_part_import, ["--interactive", "twice-add", "--help"])
    assert result.exit_code == 0
    assert "twice-add" in result.output
    assert "allows creating missing categories" in result.output
    assert "parameters from DigiKey data" in result.output
