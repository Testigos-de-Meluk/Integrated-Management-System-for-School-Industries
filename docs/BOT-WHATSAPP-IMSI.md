# Bot de WhatsApp / importación de chats — IMSI

Fecha: 2026-11-28
Base: remoto `feat/first-release`, SHA `410ef36aa803bcdab9cd04151d488a7e772cbe81`.

## 1. Aclaración de rol: no es un bot conversacional de WhatsApp

En el proyecto hay dos cosas distintas:

### 1.1 `chatbot` — asistente público del portal

- Módulo: `backend/modules/chatbot/`.
- Rutas: `/api/chatbot/catalog/`, `/assistant/`, `/proposal/`, `/estimate/`, `/quotations/`, PDF y correo.
- Es un asistente REST para el portal público `/cotizar`.
- Propone productos a partir de texto libre y estima rangos de precio.
- **No fija precios finales, no aprueba cotizaciones y no recibe WhatsApp.**
- Implementado en 4a/4b/4c.

### 1.2 `price_history` — importación de chats exportados de WhatsApp

- Módulo: `backend/modules/price_history/`.
- Requisito: FR-02-24; historias US 2.42 y US 2.43.
- Es una **fuente de datos históricos de precios**, no un canal de conversación.
- Un Administrador/Superadministrador sube un chat exportado (`.txt` preferido; imágenes si el proveedor puede leerlas).
- El sistema extrae muestras candidatas: producto, cantidad, precio unitario y fecha.
- Las muestras quedan **pendientes de revisión**; el administrador las asocia al catálogo y confirma o descarta.
- Solo las muestras confirmadas alimentan el estimador de precios.
- El archivo original se elimina después de la extracción; las muestras no guardan datos personales.
- Estado actual: **no implementado**. `price_history/infrastructure/api/urls.py` sigue con `urlpatterns: list = []`; no hay extractor ni flujo de revisión.

### 1.3 Si lo que quieres es que el bot arme cotizaciones

Eso **no es** el chatbot actual ni el import de precios. Sería un flujo nuevo, por ejemplo `WhatsAppQuoteIntake`:

- Recibe un chat exportado.
- Extrae productos, cantidades, cliente y fechas.
- Crea una **cotización preliminar** en estado pendiente.
- Un humano la revisa; nunca se aprueba sola.
- No reemplaza al chatbot público; es otro canal de entrada batch.

Hay que decidirlo antes de programar: **¿muestras de precio o cotización preliminar?** El documento cubre ambas, separadas.

## 2. Formato real de los chats

Ruta de los 220 chats de cotizaciones:

`C:/Users/cjcue/.omp-workspace/.worktrees/anonimizacion-cotizaciones/ingenieria-software-2/whatsapp-cotizaciones/chats/cotizaciones`

Cada carpeta es un chat y contiene:

- `chat.md`
- `chat.txt`

Conteos observados en 220 chats:

- 220 `chat.md` + 220 `chat.txt`.
- 6.535 mensajes con timestamp en cada formato.
- 6 bloques vCard.
- 359 `<documento omitido>`.
- 236 `[Reenviado]`.
- 27 URLs `https://`.
- 302 citas `>` en Markdown.

### 2.1 `chat.txt` — formato nativo preferido

Ejemplo de forma, sin datos reales:

```text
Los mensajes y las llamadas están cifrados de extremo a extremo...

[9/11/26, 12:00:00 PM] - Los mensajes y las llamadas están cifrados...
[9/11/26, 12:00:05 PM] Nombre: Hola, necesito cotizar...
[9/11/26, 12:01:10 PM] +57 300 000 0000: ¿Me confirma cantidad?
[9/11/26, 12:02:00 PM] Nombre: <documento omitido>
```

Patrones:

- Timestamp: `[M/D/YY, h:mm:ss AM/PM]`.
- También puede aparecer sin segundos o con `a. m./p. m.` si el locale cambia.
- Mensaje del sistema: línea que empieza con `-` o con el aviso de cifrado.
- Hablante: `Nombre:` o teléfono `+57 ...:`.
- `Tú:` puede aparecer como hablante propio.
- Multimedia/documento: `<documento omitido>`, `<multimedia omitido>`, `[Documento]`, `[Reenviado]`.
- vCard: bloque `BEGIN:VCARD` ... `END:VCARD`, con `FN`, `N`, `ORG`, `TEL`, `EMAIL`, `ADR` y líneas plegadas.
- URLs y texto libre con `:` no deben romper el parser.

### 2.2 `chat.md` — derivado Markdown

```markdown
# Exportación de chat de WhatsApp: <título>

## September 11, 2026

[12:00:00 PM] **Nombre:** Hola...
```

- Primera línea: `# Exportación de chat de WhatsApp: ...`.
- Fechas: `## Month DD, YYYY`.
- Mensajes: `[timestamp] **Hablante:** texto`.
- Citas: líneas `>`.
- vCard y adjuntos también aparecen.

**Recomendación:** el bot debe usar `chat.txt` como formato canónico porque es el más cercano a la exportación nativa. `chat.md` se puede aceptar como variante, pero no como única fuente.

### 2.3 Reglas del parser

- Leer UTF-8 con y sin BOM.
- Aceptar `\n` y `\r\n`.
- No asumir que el nombre de la carpeta es el cliente: puede ser teléfono o alias.
- No asumir que la primera línea es un mensaje.
- No romper con `:` dentro del texto, URLs o emojis.
- Separar timestamp, hablante y cuerpo.
- Preservar el orden y la fecha.
- Ignorar el aviso de cifrado y los eventos de sistema.
- Detectar vCard antes de intentar partir por `:`.
- Convertir `<documento omitido>` en `attachment_missing`, no en producto.
- Marcar `[Reenviado]` como `forwarded=true`.
- No guardar el archivo original más allá de la extracción.

## 3. Qué debe hacer el pipeline

### 3.1 Flujo de muestras de precio (FR-02-24)

1. Administrador sube `chat.txt` (o imagen, si hay OCR/visión).
2. Se calcula hash; si ya existe, se rechaza o se reutiliza el lote.
3. Se guarda temporalmente en almacenamiento privado.
4. Se parsean mensajes y se agrupan por conversación.
5. El extractor (LLM + reglas) propone muestras:
   - producto (texto),
   - cantidad,
   - precio unitario,
   - moneda,
   - fecha del mensaje,
   - evidencia (mensaje),
   - confianza.
6. Se validan fechas, moneda, cantidades y precios.
7. Las muestras quedan `PENDING_REVIEW`.
8. El administrador las asocia a un producto del catálogo y confirma o descarta.
9. Solo las confirmadas pasan al estimador.
10. Se elimina el archivo original y se audita el lote.

### 3.2 Flujo de cotización preliminar (`WhatsAppQuoteIntake`, si se decide)

1. Subir/ingerir chat.
2. Extraer cliente, productos, cantidades, fechas y observaciones.
3. Crear `QuoteDraft` en `PENDING_REVIEW`.
4. El administrador revisa y corrige.
5. Al aprobar, se crea una cotización normal del módulo `quotations`.
6. El bot nunca fija precio final ni aprueba.

## 4. Modelo de datos propuesto

### 4.1 Muestras de precio

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
- `evidence` text (sin datos personales)
- `created_at`, `reviewed_by`, `reviewed_at`

### 4.2 Cotización preliminar (si aplica)

- `QuoteDraft`: `id`, `source_chat_hash`, `customer_name`, `customer_tax_id`, `requested_at`, `status`, `created_by`, `reviewed_by`.
- `QuoteDraftItem`: `id`, `draft_id`, `product_id` nullable, `product_text`, `quantity`, `unit`, `notes`, `confidence`.
- No guardar el chat completo; solo evidencia mínima y sin PII.

## 5. Arquitectura hexagonal

Módulo `price_history` (o nuevo `whatsapp_intake`):

- **Dominio:** `PriceImportBatch`, `HistoricalPriceSample`, reglas de validación.
- **Puertos de entrada:** `PriceHistoryImport` (subir, listar, confirmar, descartar).
- **Puertos de salida:**
  - `WhatsAppChatParser`
  - `PriceSampleExtractor`
  - `PriceSampleRepository`
  - `PriceImportBatchRepository`
  - `TemporaryFileStorage`
  - `AuditLogger`
- **Adaptadores:**
  - `TextWhatsAppChatParser` (stdlib)
  - `DeepSeekPriceSampleExtractor` (adaptador del `LanguageModel` existente, no llamar a DeepSeek desde el dominio)
  - `PostgresPriceSampleRepository`
  - `LocalTemporaryFileStorage`
  - `DjangoAuditLogger`
- **Entrada:** `PriceHistoryImportView` + `POST /api/price-history/import/`.
- **Worker:** tarea Celery o management command; no bloquear el request HTTP.

Regla: el dominio no importa `requests`, `openai`, `boto3` ni Django. El proveedor de IA se cambia por configuración.

## 6. Configuración

### 6.1 Variables de entorno

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

Reutilizar las variables existentes del proveedor:

```dotenv
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_SESSION_HEADER=
```

`LLM_API_KEY` va en el store de secretos, nunca en logs ni en el repositorio.

### 6.2 Permisos

- `PRICE_HISTORY_IMPORT`: Administrador y Superadministrador.
- Operador: denegado.
- Revisión de muestras: Administrador/Superadministrador.
- Audit `PRICE_IMPORT_CREATED`, `PRICE_IMPORT_FAILED`, `PRICE_SAMPLE_CONFIRMED`, `PRICE_SAMPLE_DISCARDED`.

### 6.3 API propuesta

```text
POST   /api/price-history/import/            multipart .txt
GET    /api/price-history/import/            lista de lotes
GET    /api/price-history/import/<id>/       estado y conteos
GET    /api/price-history/samples/           filtro status=PENDING_REVIEW
POST   /api/price-history/samples/<id>/confirm/
POST   /api/price-history/samples/<id>/discard/
```

Para cotización preliminar, usar prefijo separado:

```text
POST   /api/whatsapp-intake/import/
GET    /api/whatsapp-intake/drafts/
POST   /api/whatsapp-intake/drafts/<id>/review/
```

No mezclar estos endpoints con `/api/chatbot/`.

### 6.4 Prompt del extractor

Debe devolver JSON estricto, por ejemplo:

```json
{
  "samples": [
    {
      "product_text": "...",
      "quantity": "40",
      "unit_price": "125000",
      "currency": "COP",
      "message_date": "2026-09-11",
      "evidence": "texto mínimo sin datos personales",
      "confidence": 0.82
    }
  ]
}
```

Reglas del prompt:

- No inventar precios.
- Si falta precio o cantidad, dejar `null` y bajar confianza.
- No extraer datos personales.
- No devolver precios finales de cotización.
- Una muestra por producto/mensaje.
- Fechas en ISO.
- Si no hay muestras, devolver `{"samples": []}`.

### 6.5 Almacenamiento y privacidad

- Guardar el archivo temporal en un directorio privado.
- Hash SHA-256 para idempotencia.
- Borrar el archivo después de extraer.
- No guardar el chat completo en la base.
- No loguear mensajes ni PII.
- Limitar tamaño, líneas y muestras.
- Escanear el archivo por extensión real, no solo por nombre.
- Rechazar rutas, ZIPs anidados y binarios inesperados.

## 7. Cómo añadirlo al proyecto

1. Crear el módulo `price_history` con dominio, puertos y adaptadores (el esqueleto existe; `api/urls.py` está vacío).
2. Implementar `TextWhatsAppChatParser`.
3. Implementar `PriceSampleExtractor` con el `LanguageModel` compartido.
4. Crear migraciones `PriceImportBatch` y `HistoricalPriceSample`.
5. Implementar `PriceHistoryImportService` (subida, parseo, extracción, revisión).
6. Exponer API y permisos.
7. Añadir tarea Celery/worker y estado de lote.
8. Añadir pantalla de importación y revisión.
9. Añadir auditoría y borrado del original.
10. Añadir feature flag y documentación.

No crear un `WhatsAppBot` que converse si el requisito es importar archivos. Si se necesita conversación real, eso es WhatsApp Business API y un módulo distinto.

## 8. Tests

### 8.1 Tests del parser (unitarios)

Fixtures sintéticos, nunca chats reales:

- `chat.txt` con `[M/D/YY, h:mm:ss AM/PM]`.
- Variante sin segundos.
- Variante `a. m./p. m.`.
- `chat.md` con `## Month DD, YYYY`.
- Hablante `Nombre:`, `+57 ...:`, `Tú:`.
- Texto con `:` y URL.
- Multilínea.
- `<documento omitido>`, `[Reenviado]`, `[Documento]`.
- vCard con `FN`, `N`, `ORG`, `TEL`, `EMAIL`, `ADR`, líneas plegadas.
- Aviso de cifrado y eventos de sistema.
- BOM, CRLF, archivo vacío, línea truncada.
- Nombre de carpeta con teléfono: no usarlo como cliente.

Criterios:

- Mismo número de mensajes que `chat.txt`.
- Orden y timestamps preservados.
- vCard no se parte por `:`.
- Adjuntos no se convierten en productos.

### 8.2 Tests del extractor (mock LLM)

- JSON válido con una y varias muestras.
- Precio ausente → `null`, confianza baja.
- Cantidad ausente.
- Moneda distinta de COP.
- Fecha inválida.
- Producto desconocido.
- Texto ambiguo.
- Prompt injection dentro del chat.
- Respuesta malformada.
- Timeout, error de red, reintento.
- No se llamó al proveedor real.

### 8.3 Tests de integración

- Subida `.txt` → lote `PENDING_REVIEW`.
- Archivo original borrado.
- Hash duplicado no crea otro lote.
- Extensión no permitida → 400.
- Archivo demasiado grande → 413.
- Usuario sin `PRICE_HISTORY_IMPORT` → 403.
- Fallo del extractor → lote `FAILED`, sin muestras.
- Confirmar muestra sin producto → 400.
- Confirmar muestra → solo entonces entra al estimador.
- Descartar muestra → no entra.
- Auditoría de cada acción.

### 8.4 Tests de flujos del sistema

1. **Precio histórico:** chat exportado → import → muestra pendiente → confirmar → estimador la usa como referencia → cotización.
2. **Cotización preliminar (si se implementa):** chat → draft → revisión → cotización aprobada → O.T. → cola de exportación.
3. **Duplicados:** mismo chat dos veces → un solo lote.
4. **Privacidad:** archivo eliminado, sin PII en muestras, logs y auditoría.
5. **Prompt injection:** un mensaje intenta cambiar instrucciones → el extractor no ejecuta ni filtra datos.
6. **Carga:** 220 chats / 6.535 mensajes; medir tiempo, memoria y límites.
7. **Concurrencia:** dos administradores suben a la vez; no se pisan lotes.
8. **Regresión:** el chatbot público sigue funcionando sin cambios.

### 8.5 Tests de seguridad

- Sin secretos en logs.
- Sin PII en muestras.
- Sin path traversal.
- Sin archivos ejecutables.
- Sin respuestas del LLM que se usen como SQL/comandos.
- Rate limit en endpoints públicos; permisos en privados.

## 9. Preguntas abiertas

1. ¿El objetivo es **muestras de precio** o **cotizaciones preliminares**?
2. ¿Se aceptan solo `.txt` o también capturas/OCR?
3. ¿Qué proveedor de IA se usará en producción?
4. ¿Quién revisa y con qué permiso?
5. ¿Se guarda evidencia mínima o el mensaje completo?
6. ¿Qué retención tiene el lote?
7. ¿El bot debe responder por WhatsApp o solo importar archivos?
8. ¿Cómo se evita que un chat real con PII entre al repositorio o a los tests?

## 10. Referencias

- Remoto: `https://github.com/Testigos-de-Meluk/Integrated-Management-System-for-School-Industries`, rama `feat/first-release`, SHA `410ef36`.
- `backend/modules/chatbot/infrastructure/api/urls.py`: rutas públicas del asistente.
- `backend/modules/price_history/infrastructure/api/urls.py`: `urlpatterns: list = []` (sin implementar).
- `backend/modules/shared_kernel/infrastructure/llm/openai_compatible.py`: adaptador de IA existente.
- `CLAUDE.md`: chatbot 4a/4b/4c; `price_history` pendiente; WhatsApp no es canal.
- `Workshops/Corrections/README.md`: FR-02-24, US 2.42, US 2.43, NFR-08-02.
- Chats de formato: `C:/Users/cjcue/.omp-workspace/.worktrees/anonimizacion-cotizaciones/ingenieria-software-2/whatsapp-cotizaciones/chats/cotizaciones` (220 pares `chat.md`/`chat.txt`).
- Versión anonimizada: `C:/Users/cjcue/.omp-workspace/.worktrees/anonimizacion-cotizaciones/ingenieria-software-2/whatsapp-cotizaciones/chats-anonimizados/cotizaciones`.
