# McMaster Integration TODO

- [x] Step 1: Update `ApiPart` and helper functions for authenticated downloads
    - [x] Update `ApiPart` in `inventree_part_import/suppliers/base.py`
    - [x] Update `upload_image`, `upload_datasheet`, `_download_file_content` in `inventree_part_import/inventree_helpers.py`
    - [x] Update `PartImporter.import_supplier_part` in `inventree_part_import/part_importer.py`
- [x] Step 2: Implement `McMasterApi` class with mTLS and login flow
- [x] Step 3: Implement `McMaster` supplier class with auto-subscription and search
- [x] Step 4: Verification
