import os
from pathlib import Path
from typing import Any, cast

import dlt
import duckdb
from error_helper import error, info
from requests import Session
from requests.exceptions import HTTPError

from ..retries import setup_session
from .base import ApiPart, Supplier, SupplierSupportLevel, money2float


@dlt.source
def mcmaster_source(api: "McMasterApi", part_number: str):
    """dlt source for McMaster-Carr product data."""

    @dlt.resource(name="products", write_disposition="merge", primary_key="PartNumber")
    def product_resource():
        yield api.get_product(part_number)

    @dlt.resource(name="prices", write_disposition="append")
    def price_resource():
        price_data = api.get_price(part_number)
        if price_data:
            for entry in price_data:
                entry["PartNumber"] = part_number
                yield entry

    return [product_resource, price_resource]


class McMaster(Supplier):
    SUPPORT_LEVEL = SupplierSupportLevel.OFFICIAL_API

    def setup(self, *, cert: str, username: str, password: str, currency: str = "USD", **kwargs: Any):
        self.currency = currency
        self.api = McMasterApi(cert, username, password)
        self.db_path = Path("data") / "mcmaster.duckdb"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def search(self, search_term: str) -> tuple[list[ApiPart], int]:
        # Stage 1: API to DuckDB via dlt
        pipeline = dlt.pipeline(
            pipeline_name="mcmaster_pipeline",
            destination="duckdb",
            dataset_name="mcmaster_data",
        )
        
        # Configure DuckDB destination path
        os.environ["DESTINATION__DUCKDB__CREDENTIALS"] = f"duckdb:///{self.db_path.absolute()}"
        
        try:
            info(f"Syncing {search_term} to local DuckDB ...")
            pipeline.run(mcmaster_source(self.api, search_term))
        except HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return [], 0
            raise e

        # Stage 2: DuckDB to ApiPart
        with duckdb.connect(str(self.db_path)) as conn:
            # Reconstruct product data from DuckDB
            product_rows = conn.execute(
                "SELECT * FROM mcmaster_data.products WHERE part_number = ?", 
                [search_term]
            ).df()
            
            if product_rows.empty:
                return [], 0
            
            # dlt might have flattened specifications, but we want the original-ish structure
            # if we can, or at least enough to satisfy get_api_part.
            # Since we yield the raw dict to dlt, we can fetch it back.
            product = product_rows.to_dict("records")[0]
            
            # Fetch price breaks
            price_rows = conn.execute(
                "SELECT * FROM mcmaster_data.prices WHERE part_number = ?",
                [search_term]
            ).df()
            price_data = price_rows.to_dict("records")

        api_part = self.get_api_part(product, price_data)
        return [api_part], 1

    def get_api_part(self, product: dict[str, Any], price_data: list[dict[str, Any]]):
        part_number = product["part_number"]
        
        price_breaks = {}
        packaging = ""
        if price_data:
            for entry in price_data:
                price_breaks[entry["minimum_quantity"]] = float(entry["amount"])
                if not packaging:
                    packaging = entry.get("unit_of_measure", "")

        # Extract specifications
        # dlt might have flattened these if they were a list of dicts.
        # However, for a single record 'merge' it usually keeps them if possible 
        # or flattens into separate tables. 
        # For simplicity in this two-stage, we rely on the fact that dlt-duckdb
        # allows querying the data back.
        
        # Note: dlt flattens nested lists into child tables by default.
        # We might need to query 'mcmaster_data.products__specifications'
        parameters = {}
        with duckdb.connect(str(self.db_path)) as conn:
            spec_rows = conn.execute(
                "SELECT attribute, values FROM mcmaster_data.products__specifications "
                "WHERE _dlt_parent_id = ?",
                [product["_dlt_id"]]
            ).fetchall()
            for attr, vals in spec_rows:
                # dlt might store 'values' as a JSON string or in another child table
                # if it's a list of strings.
                if isinstance(vals, str):
                    parameters[attr] = vals
                else:
                    parameters[attr] = str(vals)

            # Extract links
            links = {}
            link_rows = conn.execute(
                "SELECT key, value FROM mcmaster_data.products__links "
                "WHERE _dlt_parent_id = ?",
                [product["_dlt_id"]]
            ).fetchall()
            links = {key: val for key, val in link_rows}

        image_url = ""
        datasheet_url = ""
        if image_path := links.get("Image"):
            image_url = f"{McMasterApi.BASE_URL}{image_path}"
        
        if ds_path := links.get("Datasheet") or links.get("Data Sheet"):
            datasheet_url = f"{McMasterApi.BASE_URL}{ds_path}"

        return ApiPart(
            description=product.get("detail_description", ""),
            image_url=image_url or None,
            datasheet_url=datasheet_url or None,
            supplier_link=f"https://www.mcmaster.com/{part_number}",
            SKU=part_number,
            manufacturer="McMaster-Carr",
            manufacturer_link="",
            MPN=part_number,
            quantity_available=True if product.get("product_status") == "Active" else 0,
            packaging=packaging,
            category_path=[product.get("family_description", "")],
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
