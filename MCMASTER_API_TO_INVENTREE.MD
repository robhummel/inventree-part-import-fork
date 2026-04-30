# McMaster-Carr API to InvenTree Integration

This document describes the technical architecture implemented to bridge McMaster-Carr’s product data into a local library and synchronize it with **InvenTree**.

---

## Phase 1: Connecting to the McMaster-Carr API
Connecting to McMaster-Carr is complex because they use **mTLS (mutual TLS)** and a **double-authentication** flow. We solved this using a custom `dlt` source.

### 1. Secure mTLS Handshake
Unlike standard APIs, McMaster-Carr requires a client certificate. We:
*   Converted the official `.pfx` certificate to a `.pem` format using OpenSSL.
*   Implemented a custom **`InsecureSession`** in Python. This session automatically attaches the certificate to every single request and handles SSL verification logic, ensuring the secure handshake happens before any data is exchanged.

### 2. The Login Flow
McMaster-Carr uses a session-based Bearer token. We built a custom **`McMasterAuth`** class that:
1.  Intercepts the first request.
2.  Performs a `POST /v1/login` using API credentials.
3.  Extracts the `AuthToken` from the response.
4.  Automatically injects `Authorization: Bearer <token>` into all subsequent headers.

### 3. Intelligent Ingestion Pattern
Because McMaster-Carr uses a **subscription model**, you cannot browse their catalog. We used a **`dlt.transformer`** pattern:
*   **The Trigger:** A list of part numbers is provided (e.g., `90600A134`).
*   **Auto-Subscription:** If the API reports you aren't subscribed to a part, the pipeline automatically issues a `PUT` request to subscribe, then immediately retries the fetch.
*   **Deep Extraction:** It fetches the main product specs AND the current market price in parallel.

---

## Phase 2: The InvenTree Import Model
By adding a **Custom Destination** to the pipeline, we map McMaster’s raw data directly to InvenTree’s schema.

| McMaster-Carr Field | InvenTree Field | Example Value |
| :--- | :--- | :--- |
| `PartNumber` | **IPN / Name** | `90600A134` |
| `DetailDescription` | **Description** | `18-8 Stainless Steel Button Head Torx Screws` |
| `FamilyDescription` | **Category** | `Screws and Bolts` (mapped to InvenTree ID) |
| `Amount` (Price) | **Purchase Cost** | `$10.58` |
| `UnitOfMeasure` | **Units** | `Packs` |
| `Link (3-D STEP)` | **Attachment** | *Automated download to InvenTree Part Files* |
| `Link (Image)` | **Part Image** | *Automated upload to InvenTree thumbnail* |

### The User Experience in InvenTree
1.  **Part Creation:** Adding a part number to the list and running the script creates a new Part record in InvenTree instantly.
2.  **Metadata Enrichment:** Specifications (Material, Thread Size, Length) are saved as **Parameter Templates** in InvenTree, making the inventory searchable by physical dimensions.
3.  **File Sync:** The pipeline follows CAD/Image links, downloads the files, and uploads them to the "Attachments" or "Image" fields in InvenTree.
4.  **Automatic Pricing:** Subsequent runs update the "Supplier Part" price, ensuring Bill of Materials (BOM) costs are always accurate.

---

## Technical Advantage of dlt
`dlt` acts as the **"Traffic Controller"** between these two systems. It handles:
*   **Deduplication:** It remembers what has already been imported and only updates changes (like price).
*   **Schema Evolution:** If McMaster adds new fields, `dlt` detects and maps them without requiring code changes.
*   **Resiliency:** Built-in retries for network timeouts or API rate-limiting.
