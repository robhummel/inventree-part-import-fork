import unittest
from unittest.mock import MagicMock, patch
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

    def test_get_api_part(self):
        product_data = {
            "PartNumber": "90600A134",
            "ProductStatus": "Active",
            "FamilyDescription": "Screws",
            "DetailDescription": "18-8 Stainless Steel Button Head Torx Screws",
            "Specifications": [
                {"Attribute": "Material", "Values": ["18-8 Stainless Steel"]},
                {"Attribute": "Thread Size", "Values": ["1/4\"-20"]}
            ],
            "Links": [
                {"Key": "Price", "Value": "/v1/products/90600A134/price"},
                {"Key": "Image", "Value": "/v1/images/some_image.png"},
                {"Key": "Data Sheet", "Value": "/v1/datasheets/some_ds.pdf"}
            ]
        }
        price_data = [
            {"Amount": 10.58, "MinimumQuantity": 1, "UnitOfMeasure": "Pack of 50"}
        ]
        
        self.mcmaster.api.get_price = MagicMock(return_value=price_data)
        
        api_part = self.mcmaster.get_api_part(product_data)
        
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

    @patch("inventree_part_import.suppliers.supplier_mcmaster.McMasterApi.get_product")
    def test_search_success(self, mock_get_product):
        product_data = {"PartNumber": "123", "ProductStatus": "Active"}
        mock_get_product.return_value = product_data
        
        # Mock get_price since get_api_part calls it
        self.mcmaster.api.get_price = MagicMock(return_value=[])
        
        results, count = self.mcmaster.search("123")
        
        self.assertEqual(count, 1)
        self.assertEqual(results[0].SKU, "123")

    @patch("inventree_part_import.suppliers.supplier_mcmaster.McMasterApi.get_product")
    def test_search_not_found(self, mock_get_product):
        from requests.exceptions import HTTPError
        from requests import Response
        
        response = Response()
        response.status_code = 404
        mock_get_product.side_effect = HTTPError(response=response)
        
        results, count = self.mcmaster.search("nonexistent")
        
        self.assertEqual(count, 0)
        self.assertEqual(results, [])

if __name__ == "__main__":
    unittest.main()
