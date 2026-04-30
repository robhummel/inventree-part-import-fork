import os
from typing import Any, cast

from error_helper import error, info
from requests import Session
from requests.exceptions import HTTPError

from ..retries import setup_session
from .base import ApiPart, Supplier, SupplierSupportLevel, money2float


class McMaster(Supplier):
    SUPPORT_LEVEL = SupplierSupportLevel.OFFICIAL_API

    def setup(self, *, cert: str, username: str, password: str, currency: str = "USD", **kwargs: Any):
        self.currency = currency
        self.api = McMasterApi(cert, username, password)

    def search(self, search_term: str) -> tuple[list[ApiPart], int]:
        try:
            product = self.api.get_product(search_term)
        except HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return [], 0
            raise e

        if not product:
            return [], 0

        api_part = self.get_api_part(product)
        return [api_part], 1

    def get_api_part(self, product: dict[str, Any]):
        part_number = product["PartNumber"]
        
        # Fetch price information
        price_data = self.api.get_price(part_number)
        price_breaks = {}
        packaging = ""
        if price_data:
            # McMaster returns a list of price breaks
            for entry in price_data:
                price_breaks[entry["MinimumQuantity"]] = float(entry["Amount"])
                if not packaging:
                    packaging = entry.get("UnitOfMeasure", "")

        # Extract specifications
        parameters = {
            spec["Attribute"]: ", ".join(spec["Values"])
            for spec in product.get("Specifications", [])
        }

        # Extract links
        image_url = ""
        datasheet_url = ""
        links = {link["Key"]: link["Value"] for link in product.get("Links", [])}
        
        if image_path := links.get("Image"):
            image_url = f"{McMasterApi.BASE_URL}{image_path}"
        
        # We prefer "Datasheet" but might find other relevant links
        if ds_path := links.get("Datasheet") or links.get("Data Sheet"):
            datasheet_url = f"{McMasterApi.BASE_URL}{ds_path}"

        return ApiPart(
            description=product.get("DetailDescription", ""),
            image_url=image_url or None,
            datasheet_url=datasheet_url or None,
            supplier_link=f"https://www.mcmaster.com/{part_number}",
            SKU=part_number,
            manufacturer="McMaster-Carr",
            manufacturer_link="",
            MPN=part_number,
            quantity_available=True if product.get("ProductStatus") == "Active" else 0,
            packaging=packaging,
            category_path=[product.get("FamilyDescription", "")],
            parameters=parameters,
            price_breaks=price_breaks,
            currency=self.currency,
            session=self.api.session,
        )


class McMasterApi:
    BASE_URL = "https://api.mcmaster.com"

    def __init__(self, cert: str, username: str, password: str):
        self.cert = cert
        self.username = username
        self.password = password
        self.session = setup_session()
        
        if not os.path.exists(cert):
            error(f"McMaster-Carr certificate not found at {cert}")
            raise FileNotFoundError(cert)
            
        self.session.cert = cert
        self.token = None
        self._login()

    def _login(self):
        info("Logging in to McMaster-Carr API ...")
        url = f"{self.BASE_URL}/v1/login"
        body = {
            "UserName": self.username,
            "Password": self.password
        }
        
        # We don't use self.session.post here yet because we don't have the token,
        # but we need the cert.
        response = self.session.post(url, json=body)
        response.raise_for_status()
        
        data = response.json()
        self.token = data["AuthToken"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.BASE_URL}{path}"
        
        for _ in range(2):  # Retry once if token expires
            response = self.session.request(method, url, **kwargs)
            
            if response.status_code == 403:
                try:
                    error_data = response.json()
                    if error_data.get("ErrorMessage") == "EXPIRED_AUTHORIZATION_TOKEN":
                        self._login()
                        continue
                    if error_data.get("ErrorMessage") == "NOT_SUBSCRIBED_TO_PRODUCT":
                        # This is handled by the caller or specialized method
                        raise HTTPError(response=response)
                except Exception:
                    pass
            
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()

    def get_product(self, part_number: str) -> dict[str, Any]:
        path = f"/v1/products/{part_number}"
        try:
            return self._request("GET", path)
        except HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                error_data = e.response.json()
                if error_data.get("ErrorMessage") == "NOT_SUBSCRIBED_TO_PRODUCT":
                    info(f"Not subscribed to {part_number}, subscribing now ...")
                    self.subscribe_to_product(part_number)
                    return self._request("GET", path)
            raise e

    def subscribe_to_product(self, part_number: str):
        path = "/v1/products"
        body = {"URL": f"https://mcmaster.com/{part_number}"}
        return self._request("PUT", path, json=body)

    def get_price(self, part_number: str) -> list[dict[str, Any]]:
        path = f"/v1/products/{part_number}/price"
        return self._request("GET", path)
