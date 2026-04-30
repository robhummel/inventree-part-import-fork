import unittest
from unittest.mock import MagicMock, patch
from inventree_part_import.suppliers.supplier_mcmaster import McMasterApi
from requests.exceptions import HTTPError
from requests import Response

class TestMcMasterApi(unittest.TestCase):
    def setUp(self):
        # Patch __init__ and _login to avoid real network/file calls
        with patch.object(McMasterApi, '__init__', return_value=None), \
             patch.object(McMasterApi, '_login', return_value=None):
            self.api = McMasterApi("fake.pem", "user", "pass")
            self.api.session = MagicMock()
            self.api.BASE_URL = "https://api.mcmaster.com"

    def test_request_token_refresh(self):
        # First call returns 403 EXPIRED_AUTHORIZATION_TOKEN
        # Second call returns 200 OK
        resp1 = Response()
        resp1.status_code = 403
        resp1._content = b'{"ErrorMessage": "EXPIRED_AUTHORIZATION_TOKEN"}'
        
        resp2 = Response()
        resp2.status_code = 200
        resp2._content = b'{"data": "ok"}'
        
        self.api.session.request.side_effect = [resp1, resp2]
        self.api._login = MagicMock()
        
        result = self.api._request("GET", "/test")
        
        self.assertEqual(result, {"data": "ok"})
        self.api._login.assert_called_once()
        self.assertEqual(self.api.session.request.call_count, 2)

    def test_get_product_auto_subscribe(self):
        # First GET /v1/products/123 returns 403 NOT_SUBSCRIBED_TO_PRODUCT
        # Second call (PUT /v1/products) returns 201 Created
        # Third call (GET /v1/products/123) returns 200 OK
        
        resp_403 = Response()
        resp_403.status_code = 403
        resp_403._content = b'{"ErrorMessage": "NOT_SUBSCRIBED_TO_PRODUCT"}'
        
        resp_put = Response()
        resp_put.status_code = 201
        resp_put._content = b'{}'
        
        resp_get_ok = Response()
        resp_get_ok.status_code = 200
        resp_get_ok._content = b'{"PartNumber": "123"}'
        
        self.api.session.request.side_effect = [resp_403, resp_put, resp_get_ok]
        
        result = self.api.get_product("123")
        
        self.assertEqual(result["PartNumber"], "123")
        self.assertEqual(self.api.session.request.call_count, 3)

if __name__ == "__main__":
    unittest.main()
