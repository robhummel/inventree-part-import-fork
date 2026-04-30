# AGENTS.MD - McMaster-Carr Integration Guide for AI Agents

## Overview
This document provides technical instructions for AI agents working on the McMaster-Carr integration in `inventree-part-import`.

## Architecture
The McMaster-Carr integration follows a two-stage import process implemented in `inventree_part_import/suppliers/supplier_mcmaster.py`. It ensures data persistence before InvenTree ingestion.

### Key Components
1.  **Stage 1: API to DuckDB (via dlt)**: 
    - A `dlt` pipeline extracts data from the McMaster-Carr API and loads it into a local DuckDB database (`./data/mcmaster.duckdb`).
    - This stage handles the **mTLS Authentication**, **Double-Authentication** (Bearer token), and **Auto-Subscription** logic.
    - Storing data first ensures that subscription states and raw product details are preserved even if the InvenTree import fails.
4.  **Bulk Sync CLI**: 
    - The `--mcmaster-sync` flag in `cli.py` allows bypassing the InvenTree import entirely.
    - It uses `Supplier.sync([part_numbers], db_path=...)` to trigger Stage 1 in bulk.
2.  **Stage 2: DuckDB to InvenTree**:
    - The `McMaster.search` method queries the local DuckDB database to reconstruct product and pricing data.
    - This data is then transformed into an `ApiPart` object for standard InvenTree import.
3.  **Authenticated Asset Downloads**: McMaster's images and datasheets are protected. The `ApiPart` object carries the authenticated `session` from the supplier to the `PartImporter`, which passes it to the download helpers in `inventree_helpers.py`.

## Implementation Details for Agents
- **Base Class**: Always inherit from `Supplier`. McMaster is an `OFFICIAL_API` support level.
- **Sync Method**: The `Supplier.sync` method is the entry point for bulk-loading data to a local DB. `McMaster.search` is refactored to call `self.sync([search_term])`.
- **Tabular Data**: `load_tabular_data_simple` in `cli.py` is used for non-interactive CSV parsing during sync tasks. It prioritizes common MPN headers.
- **dlt Source/Resources**: The `mcmaster_source` function defines how products and prices are extracted and loaded. It handles a list of part numbers for batching.
- **Database Schema**: `dlt` manages the schema in the `mcmaster_data` dataset within DuckDB. Use `duckdb.connect` to query these tables during the transformation stage.
- **Session Sharing**: If you modify how images or datasheets are downloaded, ensure you respect the `session` parameter in `upload_image`, `upload_datasheet`, and `_download_file_content`.
- **Error Handling**: The `McMasterApi._request` method handles `403 EXPIRED_AUTHORIZATION_TOKEN` by re-logging in and retrying the request once. Do not remove this logic.
- **Unit Tests**:
    - `tests/test_mcmaster.py`: Tests the supplier logic, including `dlt` pipeline triggers and DuckDB queries.
    - `tests/test_mcmaster_api.py`: Tests the underlying API client.
    - Use `unittest.mock` to mock both the network and the DuckDB database during tests.

## Maintenance Checklist
- [ ] If McMaster adds new fields, update `get_api_part` in `supplier_mcmaster.py`.
- [ ] If asset URLs change, verify the `McMasterApi.BASE_URL` prepending logic.
- [ ] Ensure `session.cert` is correctly handled if the user provides separate cert and key files (currently expects a single `.pem` containing both, or a path that `requests` understands).

## Security Note
Never log or print the `password` or `AuthToken`. The `cert` path is safe to log for debugging purposes.
