# WhatsApp Bot / Chat Import — IMSI

Date: 2026-11-28
Base: remote `feat/first-release`, SHA `410ef36aa803bcdab9cd04151d488a7e772cbe81`.

## 1. Role clarification: this is not a conversational WhatsApp bot

The project has two distinct things:

### 1.1 `chatbot` — public portal assistant

- Module: `backend/modules/chatbot/`.
- Routes: `/api/chatbot/catalog/`, `/assistant/`, `/proposal/`, `/estimate/`, `/quotations/`, PDF, and email.
- It is a REST assistant for the public `/cotizar` portal.
- It suggests products from free-form text and estimates price ranges.
- **It does not set final prices, approve quotations, or receive WhatsApp messages.**
- Implemented in 4a/4b/4c.

### 1.2 `price_history` — import of exported WhatsApp chats

- Module: `backend/modules/price_history/`.
- Requirement: FR-02-24; user stories US 2.42 and US 2.43.
- It is a **source of historical price data**, not a conversation channel.
- An Administrator/Superadministrator uploads an exported chat (`.txt` preferred; images if the provider can read them).
- The system extracts candidate samples: product, quantity, unit price, and date.
- The samples remain **pending review**; the administrator associates them with catalog products and confirms or discards them.
- Only confirmed samples feed the price estimator.
- The original file is deleted after extraction; the samples do not store personal data.
- Current status: **not implemented**. `price_history/infrastructure/api/urls.py` still contains `urlpatterns: list = []`; there is no extractor or review flow.

### 1.3 If you want the bot to build quotations

That **is not** the current chatbot or the price import. It would be a new flow, for example `WhatsAppQuoteIntake`:

- It receives an exported chat.
- It extracts products, quantities, customer, and dates.
- It creates a **preliminary quotation** in pending status.
- A human reviews it; it is never approved automatically.
- It does not replace the public chatbot; it is another batch input channel.

This must be decided before programming: **price samples or a preliminary quotation?** This document covers both, kept separate.

## 2. Actual chat format

Path to the 220 quotation chats:

`C:/Users/cjcue/.omp-workspace/.worktrees/anonimizacion-cotizaciones/ingenieria-software-2/whatsapp-cotizaciones/chats/cotizaciones`

Each folder is one chat and contains:

- `chat.md`
- `chat.txt`

Counts observed across 220 chats:

- 220 `chat.md` + 220 `chat.txt`.
- 6,535 timestamped messages in each format.
- 6 vCard blocks.
- 359 `<documento omitido>`.
- 236 `[Reenviado]`.
- 27 `https://` URLs.
- 302 Markdown `>` quotes.

### 2.1 `chat.txt` — preferred native format

Example of the structure, without real data:

```text
Messages and calls are end-to-end encrypted...

[9/11/26, 12:00:00 PM] - Messages and calls are encrypted...
[9/11/26, 12:00:05 PM] Name: Hello, I need a quotation...
[9/11/26, 12:01:10 PM] +57 300 000 0000: Can you confirm the quantity?
[9/11/26, 12:02:00 PM] Name: <documento omitido>
```

Patterns:

- Timestamp: `[M/D/YY, h:mm:ss AM/PM]`.
- It may also appear without seconds or with `a. m./p. m.` if the locale changes.
- System message: a line starting with `-` or the encryption notice.
- Speaker: `Name:` or phone number `+57 ...:`.
- `Tú:` may appear as the self-speaker.
- Multimedia/document: `<documento omitido>`, `<multimedia omitido>`, `[Documento]`, `[Reenviado]`.
- vCard: a `BEGIN:VCARD` ... `END:VCARD` block, with `FN`, `N`, `ORG`, `TEL`, `EMAIL`, `ADR`, and folded lines.
- URLs and free-form text containing `:` must not break the parser.

### 2.2 `chat.md` — derived Markdown

```markdown
# Exportación de chat de WhatsApp: <title>

## September 11, 2026

[12:00:00 PM] **Name:** Hello...
```

- First line: `# Exportación de chat de WhatsApp: ...`.
- Dates: `## Month DD, YYYY`.
- Messages: `[timestamp] **Speaker:** text`.
- Quotes: `>` lines.
- vCards and attachments also appear.

**Recommendation:** the bot should use `chat.txt` as the canonical format because it is closest to the native export. `chat.md` can be accepted as a variant, but not as the only source.

### 2.3 Parser rules

- Read UTF-8 with and without BOM.
- Accept `\n` and `\r\n`.
- Do not assume the folder name is the customer: it may be a phone number or alias.
- Do not assume the first line is a message.
- Do not break on `:` inside text, URLs, or emojis.
- Separate timestamp, speaker, and body.
- Preserve order and date.
- Ignore the encryption notice and system events.
- Detect vCards before attempting to split on `:`.
- Convert `<documento omitido>` to `attachment_missing`, not to a product.
- Mark `[Reenviado]` as `forwarded=true`.
- Do not store the original file beyond extraction.

## 3. What the pipeline must do

### 3.1 Price sample flow (FR-02-24)

1. Administrator uploads `chat.txt` (or an image, if OCR/vision is available).
2. A hash is calculated; if it already exists, the upload is rejected or the batch is reused.
3. The file is stored temporarily in private storage.
4. Messages are parsed and grouped by conversation.
5. The extractor (LLM + rules) proposes samples:
   - product (text),
   - quantity,
   - unit price,
   - currency,
   - message date,
   - evidence (message),
   - confidence.
6. Dates, currency, quantities, and prices are validated.
7. Samples remain `PENDING_REVIEW`.
8. The administrator associates them with a catalog product and confirms or discards them.
9. Only confirmed samples pass to the estimator.
10. The original file is deleted and the batch is audited.

### 3.2 Preliminary quotation flow (`WhatsAppQuoteIntake`, if decided)

1. Upload/ingest chat.
2. Extract customer, products, quantities, dates, and notes.
3. Create `QuoteDraft` in `PENDING_REVIEW`.
4. The administrator reviews and corrects it.
5. Upon approval, a normal quotation from the `quotations` module is created.
6. The bot never sets the final price or approves.

## 4. Proposed data model

### 4.1 Price samples

`PriceImportBatch`:

- `id` UUID
- `uploaded_by` FK
- `original_filename`
- `file_hash` unique
- `status` (`UPLOADED`, `PARSING`, `EXTRACTING`, `PENDING_REVIEW`, `COMPLETED`, `FAILED`)
- `message_count`
- `sample_count`
- `error_code` / `error_detail`
- `created_at`, `processed_at`, `deleted_at`

`HistoricalPriceSample`:

- `id` UUID
- `batch_id` FK
- `product_id` FK nullable
- `product_text`
- `quantity` Decimal nullable
- `unit_price` Decimal nullable
- `currency` (COP)
- `message_date` date/datetime
- `confidence` Decimal
- `status` (`PENDING_REVIEW`, `CONFIRMED`, `DISCARDED`)
- `evidence` text (without personal data)
- `created_at`, `reviewed_by`, `reviewed_at`

### 4.2 Preliminary quotation (if applicable)

- `QuoteDraft`: `id`, `source_chat_hash`, `customer_name`, `customer_tax_id`, `requested_at`, `status`, `created_by`, `reviewed_by`.
- `QuoteDraftItem`: `id`, `draft_id`, `product_id` nullable, `product_text`, `quantity`, `unit`, `notes`, `confidence`.
- Do not store the full chat; only minimal evidence without PII.

## 5. Hexagonal architecture

`price_history` module (or a new `whatsapp_intake` module):

- **Domain:** `PriceImportBatch`, `HistoricalPriceSample`, validation rules.
- **Input ports:** `PriceHistoryImport` (upload, list, confirm, discard).
- **Output ports:**
  - `WhatsAppChatParser`
  - `PriceSampleExtractor`
  - `PriceSampleRepository`
  - `PriceImportBatchRepository`
  - `TemporaryFileStorage`
  - `AuditLogger`
- **Adapters:**
  - `TextWhatsAppChatParser` (stdlib)
  - `DeepSeekPriceSampleExtractor` (adapter for the existing `LanguageModel`; do not call DeepSeek from the domain)
  - `PostgresPriceSampleRepository`
  - `LocalTemporaryFileStorage`
  - `DjangoAuditLogger`
- **Input:** `PriceHistoryImportView` + `POST /api/price-history/import/`.
- **Worker:** Celery task or management command; do not block the HTTP request.

Rule: the domain does not import `requests`, `openai`, `boto3`, or Django. The AI provider is changed through configuration.

## 6. Configuration

### 6.1 Environment variables

```dotenv
PRICE_HISTORY_IMPORT_ENABLED=false
WHATSAPP_IMPORT_MAX_BYTES=20971520
WHATSAPP_IMPORT_TMP_DIR=/tmp/imsi-whatsapp
WHATSAPP_IMPORT_RETENTION_MINUTES=0
WHATSAPP_IMPORT_ALLOWED_EXTENSIONS=.txt
PRICE_EXTRACTOR_PROVIDER=deepseek
PRICE_EXTRACTOR_TIMEOUT_SECONDS=60
PRICE_EXTRACTOR_MAX_RETRIES=2
PRICE_SAMPLE_MIN_CONFIDENCE=0.60
PRICE_SAMPLE_MAX_PER_BATCH=500
PRICE_HISTORY_REVIEW_REQUIRED=true
PII_REDACTION=true
```

Reuse the existing provider variables:

```dotenv
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_SESSION_HEADER=
```

`LLM_API_KEY` belongs in the secret store, never in logs or the repository.

### 6.2 Permissions

- `PRICE_HISTORY_IMPORT`: Administrator and Superadministrator.
- Operator: denied.
- Sample review: Administrator/Superadministrator.
- Audit: `PRICE_IMPORT_CREATED`, `PRICE_IMPORT_FAILED`, `PRICE_SAMPLE_CONFIRMED`, `PRICE_SAMPLE_DISCARDED`.

### 6.3 Proposed API

```text
POST   /api/price-history/import/            multipart .txt
GET    /api/price-history/import/            batch list
GET    /api/price-history/import/<id>/       status and counts
GET    /api/price-history/samples/           filter status=PENDING_REVIEW
POST   /api/price-history/samples/<id>/confirm/
POST   /api/price-history/samples/<id>/discard/
```

For preliminary quotations, use a separate prefix:

```text
POST   /api/whatsapp-intake/import/
GET    /api/whatsapp-intake/drafts/
POST   /api/whatsapp-intake/drafts/<id>/review/
```

Do not mix these endpoints with `/api/chatbot/`.

### 6.4 Extractor prompt

It must return strict JSON, for example:

```json
{
  "samples": [
    {
      "product_text": "...",
      "quantity": "40",
      "unit_price": "125000",
      "currency": "COP",
      "message_date": "2026-09-11",
      "evidence": "minimal text without personal data",
      "confidence": 0.82
    }
  ]
}
```

Prompt rules:

- Do not invent prices.
- If price or quantity is missing, leave it `null` and lower confidence.
- Do not extract personal data.
- Do not return final quotation prices.
- One sample per product/message.
- Dates in ISO format.
- If there are no samples, return `{"samples": []}`.

### 6.5 Storage and privacy

- Store the temporary file in a private directory.
- SHA-256 hash for idempotency.
- Delete the file after extraction.
- Do not store the full chat in the database.
- Do not log messages or PII.
- Limit size, lines, and samples.
- Scan the file by its actual extension, not just its name.
- Reject paths, nested ZIPs, and unexpected binaries.

## 7. How to add it to the project

1. Create the `price_history` module with domain, ports, and adapters (the skeleton exists; `api/urls.py` is empty).
2. Implement `TextWhatsAppChatParser`.
3. Implement `PriceSampleExtractor` using the shared `LanguageModel`.
4. Create `PriceImportBatch` and `HistoricalPriceSample` migrations.
5. Implement `PriceHistoryImportService` (upload, parsing, extraction, review).
6. Expose the API and permissions.
7. Add a Celery/worker task and batch status.
8. Add an import and review screen.
9. Add auditing and deletion of the original file.
10. Add a feature flag and documentation.

Do not create a conversational `WhatsAppBot` if the requirement is to import files. If real-time conversation is needed, that requires WhatsApp Business API and a separate module.

## 8. Tests

### 8.1 Parser tests (unit)

Use synthetic fixtures, never real chats:

- `chat.txt` with `[M/D/YY, h:mm:ss AM/PM]`.
- Variant without seconds.
- Variant with `a. m./p. m.`.
- `chat.md` with `## Month DD, YYYY`.
- Speakers `Name:`, `+57 ...:`, `Tú:`.
- Text containing `:` and a URL.
- Multiline text.
- `<documento omitido>`, `[Reenviado]`, `[Documento]`.
- vCard with `FN`, `N`, `ORG`, `TEL`, `EMAIL`, `ADR`, and folded lines.
- Encryption notice and system events.
- BOM, CRLF, empty file, truncated line.
- Folder name containing a phone number: do not use it as the customer.

Criteria:

- Same number of messages as `chat.txt`.
- Order and timestamps preserved.
- vCard is not split on `:`.
- Attachments are not converted into products.

### 8.2 Extractor tests (mock LLM)

- Valid JSON with one and multiple samples.
- Missing price → `null`, low confidence.
- Missing quantity.
- Currency other than COP.
- Invalid date.
- Unknown product.
- Ambiguous text.
- Prompt injection inside the chat.
- Malformed response.
- Timeout, network error, retry.
- The real provider was not called.

### 8.3 Integration tests

- `.txt` upload → batch `PENDING_REVIEW`.
- Original file deleted.
- Duplicate hash does not create another batch.
- Disallowed extension → 400.
- File too large → 413.
- User without `PRICE_HISTORY_IMPORT` → 403.
- Extractor failure → batch `FAILED`, no samples.
- Confirming a sample without a product → 400.
- Confirming a sample → only then does it enter the estimator.
- Discarding a sample → it does not enter.
- Audit of every action.

### 8.4 System flow tests

1. **Historical price:** exported chat → import → pending sample → confirm → estimator uses it as a reference → quotation.
2. **Preliminary quotation (if implemented):** chat → draft → review → approved quotation → work order (O.T.) → export queue.
3. **Duplicates:** same chat uploaded twice → only one batch.
4. **Privacy:** file deleted, no PII in samples, logs, or audit records.
5. **Prompt injection:** a message attempts to change instructions → the extractor neither executes them nor leaks data.
6. **Load:** 220 chats / 6,535 messages; measure time, memory, and limits.
7. **Concurrency:** two administrators upload at the same time; batches do not overwrite each other.
8. **Regression:** the public chatbot continues to work unchanged.

### 8.5 Security tests

- No secrets in logs.
- No PII in samples.
- No path traversal.
- No executable files.
- No LLM responses used as SQL/commands.
- Rate limiting on public endpoints; permissions on private ones.

## 9. Open questions

1. Is the goal **price samples** or **preliminary quotations**?
2. Are only `.txt` files accepted, or also screenshots/OCR?
3. Which AI provider will be used in production?
4. Who reviews, and with what permission?
5. Is minimal evidence stored, or the full message?
6. What is the batch retention period?
7. Should the bot respond via WhatsApp, or only import files?
8. How do we prevent a real chat containing PII from entering the repository or tests?

## 10. References

- Remote: `https://github.com/Testigos-de-Meluk/Integrated-Management-System-for-School-Industries`, branch `feat/first-release`, SHA `410ef36`.
- `backend/modules/chatbot/infrastructure/api/urls.py`: public assistant routes.
- `backend/modules/price_history/infrastructure/api/urls.py`: `urlpatterns: list = []` (not implemented).
- `backend/modules/shared_kernel/infrastructure/llm/openai_compatible.py`: existing AI adapter.
- `CLAUDE.md`: chatbot 4a/4b/4c; `price_history` pending; WhatsApp is not a channel.
- `Workshops/Corrections/README.md`: FR-02-24, US 2.42, US 2.43, NFR-08-02.
- Format chats: `C:/Users/cjcue/.omp-workspace/.worktrees/anonimizacion-cotizaciones/ingenieria-software-2/whatsapp-cotizaciones/chats/cotizaciones` (220 `chat.md`/`chat.txt` pairs).
- Anonymized version: `C:/Users/cjcue/.omp-workspace/.worktrees/anonimizacion-cotizaciones/ingenieria-software-2/whatsapp-cotizaciones/chats-anonimizados/cotizaciones`.
