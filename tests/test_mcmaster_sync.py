import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from inventree_part_import.suppliers.supplier_mcmaster import McMaster, McMasterApi
from click.testing import CliRunner
from inventree_part_import.cli import inventree_part_import

class TestMcMasterSync(unittest.TestCase):
    def setUp(self):
        self.cert = "fake_cert.pem"
        self.username = "user"
        self.password = "pass"
        
        # Patch McMasterApi.__init__ and _login to avoid real network/file calls
        with patch.object(McMasterApi, '__init__', return_value=None), \
             patch.object(McMasterApi, '_login', return_value=None):
            self.mcmaster = McMaster()
            self.mcmaster.setup(cert=self.cert, username=self.username, password=self.password)
            self.mcmaster.api.session = MagicMock()

    @patch("dlt.pipeline")
    def test_sync_success(self, mock_dlt_pipeline):
        mock_pipeline = mock_dlt_pipeline.return_value
        mock_pipeline.run.return_value = MagicMock()
        
        part_numbers = ["123", "456"]
        results = self.mcmaster.sync(part_numbers)
        
        self.assertEqual(len(results), 2)
        self.assertTrue(results["123"])
        self.assertTrue(results["456"])
        mock_pipeline.run.assert_called_once()

    @patch("dlt.pipeline")
    def test_sync_failure(self, mock_dlt_pipeline):
        mock_pipeline = mock_dlt_pipeline.return_value
        mock_pipeline.run.side_effect = Exception("API Error")
        
        part_numbers = ["123"]
        results = self.mcmaster.sync(part_numbers)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results["123"], "API Error")

    @patch("inventree_part_import.cli.get_suppliers")
    @patch("inventree_part_import.cli.load_suppliers_config")
    @patch("inventree_part_import.cli.get_config")
    def test_cli_mcmaster_sync(self, mock_get_config, mock_load_config, mock_get_suppliers):
        runner = CliRunner()
        
        # Mock config
        mock_get_config.return_value = {"interactive": "false", "currency": "USD"}
        
        # Mock available suppliers
        mock_mcmaster = MagicMock(spec=McMaster)
        mock_mcmaster.sync.return_value = {"123": True, "456": "Error"}
        
        mock_get_suppliers.return_value = ({}, {"mcmaster": mock_mcmaster})
        mock_load_config.return_value = {"mcmaster": {"cert": "c", "username": "u", "password": "p"}}
        
        # Use option instead of subcommand
        result = runner.invoke(inventree_part_import, ["--mcmaster-sync", "123", "456"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Sync complete", result.output)
        self.assertIn("Total: 2", result.output)
        self.assertIn("Success: 1", result.output)
        self.assertIn("Failure: 1", result.output)
        self.assertIn("456: Error", result.output)
        self.assertIn("Successfully synced parts:", result.output)
        self.assertIn("123", result.output)

    @patch("inventree_part_import.cli.get_suppliers")
    @patch("inventree_part_import.cli.setup_supplier_companies")
    @patch("inventree_part_import.cli.PartImporter")
    @patch("inventree_part_import.cli.get_config")
    @patch("inventree_part_import.cli.setup_inventree_api")
    def test_cli_main_inputs(self, mock_setup_api, mock_get_config, mock_importer_cls, mock_setup_companies, mock_get_suppliers):
        runner = CliRunner()
        
        # Mock config and API
        mock_get_config.return_value = {"interactive": "false", "currency": "USD"}
        mock_setup_api.return_value = MagicMock()
        
        # Mock importer
        mock_importer = mock_importer_cls.return_value
        mock_importer.import_part.return_value = MagicMock()
        
        # Mock suppliers
        mock_get_suppliers.return_value = ({}, {})
        
        # Run main command with positional inputs
        result = runner.invoke(inventree_part_import, ["PN1", "PN2"])
        
        self.assertEqual(result.exit_code, 0)
        # Verify that importer was called with the parts
        self.assertEqual(mock_importer.import_part.call_count, 2)
        mock_importer.import_part.assert_any_call("PN1", None, None, False)
        mock_importer.import_part.assert_any_call("PN2", None, None, False)

if __name__ == "__main__":
    unittest.main()
