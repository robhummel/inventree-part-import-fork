# McMaster-Carr Part Import Integration

## Objective
Integrate the McMaster-Carr Product Information API into the `inventree-part-import` CLI tool. This will allow users to import parts, categories, specifications, pricing, images, and datasheets directly from McMaster-Carr into InvenTree.

## Key Files & Context
*   `inventree_part_import/suppliers/supplier_mcmaster.py` (New File): The new supplier module implementation.
*   `inventree_part_import/suppliers/base.py`: The base `ApiPart` data class that needs to be updated to support an optional authenticated session for downloading protected assets.
*   `inventree_part_import/inventree_helpers.py`: Helper functions (`upload_image`, `upload_datasheet`, `_download_file_content`) that need to be updated to accept and use the optional authenticated session.
*   `inventree_part_import/part_importer.py`: The `PartImporter` class that coordinates the import process and calls the upload functions.

## Implementation Steps

### 1. Update `ApiPart` and Helper Functions for Authenticated Downloads
McMaster-Carr's assets (images, datasheets) are protected by mTLS and Bearer tokens. We need to pass the authenticated session used for the API calls to the download helpers.
*   Modify `ApiPart` in `inventree_part_import/suppliers/base.py` to add an optional `session: Any | None = None` attribute.
*   Update `upload_image` and `upload_datasheet` in `inventree_part_import/inventree_helpers.py` to accept an optional `session`.
*   Update `_download_file_content` in `inventree_part_import/inventree_helpers.py` to accept the `session`. If provided, use it instead of creating a new one.
*   Update `PartImporter.import_supplier_part` in `inventree_part_import/part_importer.py` to pass `api_part.session` (if it exists) to `upload_image` and `upload_datasheet`.

### 2. Implement the McMaster-Carr Supplier
Create `inventree_part_import/suppliers/supplier_mcmaster.py`:
*   Create a `McMasterApi` class that handles:
    *   **mTLS:** Accepts a certificate path and password (or just a `.pem` certificate and key) and attaches it to a `requests.Session`.
    *   **Authentication:** Performs the `POST /v1/login` request to get the `AuthToken` and injects `Authorization: Bearer <token>` into the session headers.
    *   **API Calls:** Implements methods for `get_product`, `subscribe_to_product`, and `get_price`.
*   Create a `McMaster(Supplier)` class:
    *   Set `SUPPORT_LEVEL = SupplierSupportLevel.OFFICIAL_API`.
    *   Implement `setup()` to initialize the `McMasterApi` with credentials (`cert`, `username`, `password`).
    *   Implement `search()`:
        1.  Attempt to fetch product details via `GET /v1/products/{search_term}`.
        2.  If the API returns `403 NOT_SUBSCRIBED_TO_PRODUCT`, call `PUT /v1/products` to subscribe, then retry the `GET`.
        3.  If successful, fetch the price via `GET /v1/products/{search_term}/price`.
        4.  Parse the results into an `ApiPart`.
            *   Map `FamilyDescription` to `category_path` (as a single-element list, or parse if hierarchical).
            *   Extract `Specifications`.
            *   Map `Links` -> `Image` to `image_url` (prepend API base URL if relative).
            *   Map `Links` -> `Data Sheet` (or similar) to `datasheet_url`. **Skip CAD files (e.g., `2-D DWG`, `3-D STEP`).**
            *   Set the `session` attribute of the `ApiPart` to the `McMasterApi`'s authenticated session so the image/datasheet downloads succeed.

### 3. Error Handling and Resilience
*   Ensure that `InsecureSession` or the mTLS implementation correctly handles the certificate format expected by `requests` (a tuple of `(cert_file, key_file)` or a single file with both). The setup method should prompt the user to provide the path to the `.pem` file(s).
*   Handle token expiration. Since tokens expire after 24 hours, the `McMasterApi` should intercept `403 EXPIRED_AUTHORIZATION_TOKEN` responses, automatically re-authenticate via `POST /v1/login`, and retry the request transparently.

## Verification & Testing
*   Verify that `ApiPart` correctly stores and passes the session.
*   Verify that `inventree_helpers` uses the provided session to download files.
*   Verify that the McMaster-Carr API client correctly authenticates using the client certificate and credentials.
*   Verify that the auto-subscription logic works when searching for a new part.
*   Verify that images and datasheets are successfully downloaded and uploaded to InvenTree.
*   Verify that CAD files are ignored.