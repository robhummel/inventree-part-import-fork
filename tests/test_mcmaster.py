import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from inventree_part_import.suppliers.supplier_mcmaster import McMaster, McMasterApi
from inventree_part_import.suppliers.base import ApiPart

class TestMcMaster(unittest.TestCase):
    def setUp(self):
        self.cert = "fake_cert.pem"
        self.username = "user"
        self.password = "pass"
        
        # Patch McMasterApi.__init__ and _login to avoid real network/file calls
        with patch.object(McMasterApi, '__init__', return_value=None), \
             patch.object(McMasterApi, '_login', return_value=None):
            self.mcmaster = McMaster()
            self.mcmaster.setup(cert=self.cert, username=self.username, password=self.password)
            # Manually set the mocked api session
            self.mcmaster.api.session = MagicMock()

    @patch("duckdb.connect")
    def test_get_api_part(self, mock_connect):
        # Data as it would come from DuckDB/dlt (lowercase keys)
        product_data = {
            "part_number": "90600A134",
            "product_status": "Active",
            "family_description": "Screws",
            "detail_description": "18-8 Stainless Steel Button Head Torx Screws",
            "_dlt_id": "root_id"
        }
        price_data = [
            {"amount": 10.58, "minimum_quantity": 1, "unit_of_measure": "Pack of 50"}
        ]
        
        # Mock DuckDB queries for specifications and links
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_conn.execute.side_effect = [
            MagicMock(fetchall=lambda: [
                ("Material", "18-8 Stainless Steel"),
                ("Thread Size", "1/4\"-20")
            ]),
            MagicMock(fetchall=lambda: [
                ("Image", "/v1/images/some_image.png"),
                ("Datasheet", "/v1/datasheets/some_ds.pdf")
            ])
        ]
        
        api_part = self.mcmaster.get_api_part(product_data, price_data)
        
        self.assertEqual(api_part.SKU, "90600A134")
        self.assertEqual(api_part.MPN, "90600A134")
        self.assertEqual(api_part.description, "18-8 Stainless Steel Button Head Torx Screws")
        self.assertEqual(api_part.category_path, ["Screws"])
        self.assertEqual(api_part.parameters["Material"], "18-8 Stainless Steel")
        self.assertEqual(api_part.parameters["Thread Size"], "1/4\"-20")
        self.assertEqual(api_part.price_breaks[1], 10.58)
        self.assertEqual(api_part.packaging, "Pack of 50")
        self.assertEqual(api_part.image_url, "https://api.mcmaster.com/v1/images/some_image.png")
        self.assertEqual(api_part.datasheet_url, "https://api.mcmaster.com/v1/datasheets/some_ds.pdf")
        self.assertEqual(api_part.session, self.mcmaster.api.session)

    @patch("dlt.pipeline")
    @patch("duckdb.connect")
    @patch("inventree_part_import.suppliers.supplier_mcmaster.McMaster.get_api_part")
    def test_search_success(self, mock_get_api_part, mock_duckdb_connect, mock_dlt_pipeline):
        # Mock dlt pipeline run
        mock_pipeline = mock_dlt_pipeline.return_value
        mock_pipeline.run.return_value = MagicMock()
        
        # Mock DuckDB result for product and price
        mock_conn = mock_duckdb_connect.return_value.__enter__.return_value
        
        product_df = pd.DataFrame([{"part_number": "123", "_dlt_id": "id"}])
        price_df = pd.DataFrame([{"amount": 10, "minimum_quantity": 1}])
        
        mock_conn.execute.side_effect = [
            MagicMock(df=lambda: product_df),
            MagicMock(df=lambda: price_df)
        ]
        
        mock_get_api_part.return_value = MagicMock(SKU="123")
        
        results, count = self.mcmaster.search("123")
        
        self.assertEqual(count, 1)
        self.assertEqual(results[0].SKU, "123")
        mock_pipeline.run.assert_called_once()

    @patch("dlt.pipeline")
    def test_search_not_found(self, mock_dlt_pipeline):
        from requests.exceptions import HTTPError
        from requests import Response
        
        response = Response()
        response.status_code = 404
        mock_pipeline = mock_dlt_pipeline.return_value
        mock_pipeline.run.side_effect = HTTPError(response=response)
        
        results, count = self.mcmaster.search("nonexistent")
        
        self.assertEqual(count, 0)
        self.assertEqual(results, [])

if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main()
