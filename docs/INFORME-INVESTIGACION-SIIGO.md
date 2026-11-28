# Informe de investigación: exportación IMSI → Siigo

Fecha: 2026-11-28
Alcance: entender qué debe exportar IMSI, qué acepta Siigo Pyme 10.1 y qué se puede implementar sin licencia.

## 1. Resumen

La investigación cambió varias veces de conclusión. El primer subagente trabajó con el handoff viejo y con el clon local `imsi-verify`, y concluyó que IMSI exportaba cotizaciones. Al revisar el repositorio remoto más reciente (`feat/first-release`, SHA `410ef36`), la conclusión correcta es otra:

- La cola implementada en 5c exporta **Órdenes de Trabajo (O.T.)**.
- **5c está implementado**: modelo, API, permisos, eventos y comando de sincronización.
- **5d no está implementado**: no existe generador de archivo ni `SiigoExporter`.
- El layout de Siigo sigue **sin definirse** en el repositorio.

Del lado de Siigo:

- La vía documentada para documentos comerciales es **movimiento extracontable** en un **.xlsx generado por Siigo**, no un CSV propio.
- Los tipos documentados son `Z` pedido, `Y` orden de compra y `V` cotización.
- **No existe un tipo “O.T.”**.
- La O.T. de IMSI no tiene precios; la O.T. real de la empresa sí. Eso condiciona el archivo.

No se pudo ejecutar Siigo Pyme 10.1 porque la instalación no tiene licencia. Por eso este informe se basa en documentación oficial, archivos locales y el repositorio remoto; no en una carga real.

## 2. Cómo se investigó

### 2.1 Primer intento: `SiigoExportSpec`

Se le pidió revisar documentación, workset, Wea Angel y transcripciones. El subagente leyó el handoff local y el clon `imsi-verify`, y respondió que el diseño corregido exportaba **cotizaciones aprobadas**.

Problema: no revisó el remoto. El handoff y el clon estaban desactualizados. Ese resultado quedó obsoleto en la parte de “cotizaciones”.

### 2.2 Segundo intento: `RemoteExportAudit`

Se le pidió verificar el repositorio remoto y el SHA más reciente. Encontró:

- SHA `410ef36aa803bcdab9cd04151d488a7e772cbe81`.
- `backend/modules/accounting_export/domain/queue_entry.py` usa `work_order_id`.
- `Workshops/Corrections/README.md` §4.1 FR-02-16/17/18 dice que la cola guarda **work orders**.
- 5c está implementado; 5d no.
- No existe `SiigoExporter` ni un layout de columnas.

También detectó que el clon local `imsi-verify` tiene el módulo `accounting_export` vacío: su `infrastructure/models.py` solo tiene un docstring y `api/urls.py` tiene `urlpatterns: list = []`.

### 2.3 Tercer intento: `Siigo10Audit`

Se le pidió verificar qué acepta Siigo Pyme 10.1, usando documentación oficial y la instalación local. Encontró:

- La vía es **Interfaces → Importaciones desde Excel → Movimiento extracontable → Generar modelo**.
- Siigo genera un **.xlsx** con encabezados en la fila 5 y columnas inamovibles.
- Obligatorios: **TIPO DE DOCUMENTO**, **CÓDIGO DOCUMENTO**, **NÚMERO DE DOCUMENTO**.
- Tipos documentados: `Z` pedido, `Y` orden de compra, `V` cotización.
- No hay tipo “O.T.”.
- El CLI `EXCELSIIGO.exe` usa `GETEXT`/`PUSHEXT` y el modelo `.xlsx`.
- No se encontró un CSV libre ni un PRN vigente.
- La instalación local tiene `C:/Siigo/EXCELSIIGO.exe` y `C:/Siigo/FECHAACT.CFG`, pero no se pudo ejecutar una carga por falta de licencia.

### 2.4 Workset y Wea Angel

El workset es local: no está en el repositorio ni en internet. Es la fuente que más cambia el análisis.

Ruta:
`C:/Users/cjcue/.hermes-shared/IngSW2/workset`

Estructura real:

- `01_ventas/`
- `02_compras/`
- `03_banco/`
- `04_catalogo/`
- `05_referencias/`
- `README.md`

La carpeta de análisis no está dentro del workset: está en
`C:/Users/cjcue/.hermes-shared/IngSW2/analisis-forense` (71 archivos).

Conteos del workset:

| Zona | Contenido | Archivos |
|---|---|---:|
| `01_ventas` | facturas, cotizaciones, agregados y documentos Siigo | 4.520 |
| `01_ventas/siigo_documentos_electronicos` | 900 XML + 945 TXT + 40 JSON | 1.885 |
| `02_compras/dse` | documentos soporte electrónicos | 944 |
| `04_catalogo` | catálogo Siigo + 42 O.T de muestra | 43 |
| `05_referencias` | órdenes de pedido, pedidos clientes, listas de precios | 414 |

Extensiones globales: 4.664 PDF, 945 TXT, 900 XML, 262 XLSX, 40 JSON, 66 `.a`, 26 `.s`, 2 XLSM.

Hallazgos concretos:

1. **Catálogo Siigo real.** `04_catalogo/CATALOGO SIIGO (Creación líneas grupos y productos).xlsx` tiene 6 hojas: materia prima (tubería, lámina, madera, inyección), `PRODUCTO TERMINADO` y `KITS`. Los encabezados visibles son `LINEA`, `GRUPO`, `CODIGO`, `REFERENCIA` y `OBSERVACIONES`. Es una plantilla de catálogo Siigo, no de movimiento extracontable.
2. **O.T de muestra.** `04_catalogo/ot_muestra` tiene 42 XLSX. Una muestra tiene 3 hojas; `Hoja1` mide 29 filas x 17 columnas y tiene 31 celdas combinadas. Las etiquetas visibles son `ORDEN DE TRABAJO`, `PRODUCTO` y `CANTIDAD`. Es un formato interno de O.T, no un layout de importación Siigo.
3. **Plantilla O.T embebida.** El README del workset dice que la plantilla `VERSION: 0.1` está embebida en 1.648 de 1.657 XLSX de O.T. Al escanear los 42 XLSX de muestra buscando `VERSION: 0.1` en el XML interno, el resultado fue 0. Queda como contradicción `[NO VERIFICADO]`: puede estar en otro marcador, en otra hoja o en el universo completo, no en la muestra.
4. **XML Siigo emitido, no plantilla de importación.** Los 900 XML de `01_ventas/siigo_documentos_electronicos` tienen raíz `XMLData` y nodos `Product`, `Info`, `CompanyData`, `Customer`, `Contact`, `Request`, `Billing`. Son documentos electrónicos emitidos por Siigo (facturas/DSE), no el `.xlsx` de importación de Pyme.
5. **Análisis forense.** En `analisis-forense` están `WORKSET_W1_RESUMEN.md`, `WORKSET_W2_INFORME.md`, `HALLAZGOS-COMPLETO-DETALLADO.md`, `ORDENES_TRABAJO_RESUMEN.md`, `scan_version01.py`, `sa6_schemas_fam.py`, `version01_hits.txt`, `WORKSET_INDEX.csv`. Se usan solo por conteos/campos; no se copian clientes ni montos.
6. **Resumen de O.T.** `ORDENES_TRABAJO_RESUMEN.md` reporta **1.623 O.T extraídas**, **1.558 números únicos**, rango **2593–4875** y 54 repetidas (hasta 5 copias). Campos: O.T., cliente, NIT, contacto, celular, correo, dirección, ciudad, fechas de solicitud y entrega, productos, cantidades, valores y saldo por cobrar. No se copian clientes ni montos en este informe.

Límite: en el backup amplio aparecen 371 `.prn` y 505 `.xlt`, pero no se revisaron todos ni se asumieron como plantillas de importación. En el workset no apareció una plantilla de movimiento extracontable.

Implicación: el workset sí contiene **formatos Siigo reales de catálogo y documentos electrónicos**, pero no una plantilla de importación de movimiento extracontable de Pyme 10.1. Tampoco contiene el layout de columnas que 5d necesita. El workset es local; no está en el repo ni en internet.

## 3. Qué tiene hoy el repositorio

### 3.1 Implementado: 5c

- `backend/modules/accounting_export/domain/queue_entry.py`
- `backend/modules/accounting_export/application/export_queue_service.py`
- `backend/modules/accounting_export/infrastructure/`
- `backend/modules/accounting_export/ports/`
- `backend/tests/accounting_export/test_queue.py`
- `frontend/src/features/export-queue/ExportQueuePage.tsx`

La cola:

- Guarda O.T.
- Entra al generarse la O.T.
- Sale si se anula antes de exportar o al exportarse.
- Usa estados `PENDING_EXPORT`, `EXPORTED`, `WITHDRAWN`.
- Tiene permiso `EXPORT_QUEUE_MANAGE`.
- Tiene `sync_export_queue`.

### 3.2 No implementado: 5d

- No hay generador de archivo.
- No hay `SiigoExporter`.
- No hay `EXPORT_BATCH` funcional.
- No hay plantilla `.xlsx` validada.
- No hay prueba de carga real.

El propio `export_queue_service.py` dice que el archivo y el paso a “Registrada en Siigo” llegan en 5d. `CLAUDE.md` también deja el botón de generar archivo deshabilitado hasta 5d.

## 4. Qué acepta Siigo Pyme 10.1

Fuente oficial:
`https://siigopyme2.portaldeclientes.siigo.com/interfaces-movimiento-extracontable/`

### 4.1 Formato

- `Interfaces → Importaciones desde Excel → Movimiento extracontable`.
- Se genera un modelo `.xlsx` desde la instalación.
- Los encabezados van en la fila 5.
- No se debe cambiar la fuente, las filas de encabezado, el orden ni los nombres de columnas.
- El modelo depende de la empresa/módulos configurados.

### 4.2 Columnas y tipos

Obligatorios:

- TIPO DE DOCUMENTO
- CÓDIGO DOCUMENTO
- NÚMERO DE DOCUMENTO

Tipos documentados:

- `Z` pedido
- `Y` orden de compra
- `V` cotización

No hay un tipo “O.T.”.

Columnas opcionales:

- Tercero
- Producto
- Cantidad
- Valores
- Impuestos
- Moneda
- Comentarios
- Campos libres

### 4.3 Límites de lo verificado

No se pudo hacer una carga real. Por eso no se puede afirmar que Siigo acepte una O.T. sin valores ni que rechace una fila concreta. Lo que sí está documentado es el formato `.xlsx`, los tipos `Z/Y/V` y los campos obligatorios.

## 5. Qué dijo otra IA y qué se verificó

| Afirmación de otra IA | Resultado | Explicación |
|---|---|---|
| “Siigo importa comprobantes contables, no O.T.” | Parcialmente correcta | Siigo tiene movimiento contable y movimiento extracontable. Para pedido/cotización aplica extracontable, no un comprobante contable. No hay tipo O.T. |
| “Las plantillas Excel se generan por instalación” | Correcta | “Generar modelo” produce el `.xlsx` según la empresa/módulos. |
| “El único formato con columnas publicado es un PRN de 2017” | Falsa o no sostenida | El formato vigente documentado es el `.xlsx` del modelo extracontable. No se encontró un `.prn` en `C:/Siigo` ni en el workset. |
| “Cargar una O.T. sin cuentas contables no es posible” | Matizable | El extracontable no pide cuentas contables; sí pide valores. Sin carga real no se puede afirmar el rechazo exacto. |
| “Haz un CSV con O.T., cotización, cliente, producto, cantidad y fecha” | No viable tal cual | Siigo espera el `.xlsx` del modelo; además falta decidir `V/Z` y qué hacer con valores. |
| “Siigo Pyme 10.1 no tiene un formato útil sin licencia” | Parcialmente correcta | Sin licencia no se puede validar la carga; el formato documentado sí existe. |

## 6. Por qué fue tan confuso

1. **Planes gratuitos.** Siigo Contador gratis es contabilidad en la nube para 1 empresa. Facturación gratis es una prueba con límites. No consta que incluyan la importación extracontable de Pyme.
2. **Formato.** El repo habla de “flat file CSV/TXT”; Siigo documenta un `.xlsx` generado por la instalación.
3. **Documento.** IMSI exporta O.T. sin precios; Siigo extracontable tiene columnas de valor. La O.T. real de la empresa sí lleva precios, IVA y retención.
4. **Sin licencia.** No se pudo abrir el menú de importación ni generar la plantilla real. La verificación es documental.
5. **Layout abierto.** El repo dice que faltan columnas, separador y muestra/plantilla. No hay una definición cerrada de 5d.

## 7. Propuestas

### Propuesta A — implementar 5d como adaptador provisional

- Crear `SiigoExtracontableAdapter` con un contrato claro.
- Generar un `.xlsx` con openpyxl.
- Poner las columnas en una hoja de configuración o plantilla.
- Mapear O.T. → `V` o `Z`; decidir si se usa `Z` pedido o `V` cotización.
- Incluir: número O.T., cotización, cliente/NIT, fecha, producto, descripción, unidad, cantidad, fecha acordada.
- No incluir precios si no están en la O.T.; dejar columnas de valor vacías o en cero, marcadas como pendientes.
- Probar con un workbook sintético y tests de contrato.
- No afirmar que carga en Siigo hasta que exista una prueba real.

### Propuesta B — mock + puerto hexagonal

- `AccountingExportPort` con métodos `export_batch` y `validate`.
- `MockAccountingAdapter` para la demo.
- `SiigoExtracontableAdapter` como placeholder.
- Tests de mapeo, columnas, errores y idempotencia.
- Documentar que la integración real queda bloqueada por licencia/plantilla.

### Propuesta C — cambiar de sistema externo

Solo si se acepta cambiar el alcance:

- **Odoo Community + `l10n_co`**: 56k estrellas, localización oficial colombiana, API; más pesado.
- **ERPNext + localización CO**: 41k estrellas, API, GPL-3.0; localización colombiana de terceros.
- **Nubicta**: 19 estrellas, MIT, enfoque Colombia; joven; revisar API/tests antes de usarlo.
- **Alegra**: 15 días de prueba, API, luego pago.
- **Mock**: solo demo, no integración real.

Un cambio de este tipo requiere ADR y aceptación del stakeholder; no es solo editar el README.

### Propuesta D — buscar plantilla y hacer una prueba controlada

- Pedir a Siigo una plantilla `.xlsx` generada desde Pyme 10.1.
- Hacer una carga de prueba con una empresa demo.
- Comparar el resultado con la documentación.
- Si no hay licencia, buscar en internet una plantilla oficial publicada o un ejemplo verificable; no asumir columnas.

## 8. Preguntas abiertas

1. ¿El destino es O.T., cotización o pedido?
2. ¿El tipo Siigo es `Z` o `V`?
3. ¿Qué columnas exactas debe llevar el `.xlsx`?
4. ¿Se incluyen precios/IVA o la O.T. queda sin valores?
5. ¿La numeración `OT-YYYYMMDD-NNNNN` se mapea a un consecutivo numérico?
6. ¿Se acepta un adaptador provisional sin carga real?
7. ¿Se acepta cambiar de alcance a Odoo/Nubicta/Alegra?
8. ¿Qué evidencia se necesita para considerar 5d terminado?

## 9. Referencias

### Repositorio remoto

- `https://github.com/Testigos-de-Meluk/Integrated-Management-System-for-School-Industries`
- Rama `feat/first-release`
- SHA `410ef36aa803bcdab9cd04151d488a7e772cbe81`
- `backend/modules/accounting_export/domain/queue_entry.py`
- `backend/modules/accounting_export/application/export_queue_service.py`
- `backend/modules/accounting_export/ports/outbound/ports.py`
- `backend/tests/accounting_export/test_queue.py`
- `Workshops/Corrections/README.md` §4.1 FR-02-16/17/18; §7 ítem 2; NFR-06-02
- `CLAUDE.md`

### Subagentes

- `agent://RemoteExportAudit`: auditoría del remoto `410ef36`.
- `agent://Siigo10Audit`: auditoría de Siigo Pyme 10.1.
- `agent://SiigoExportSpec`: primer informe; obsoleto en “cotizaciones”.

### Siigo

- `https://siigopyme2.portaldeclientes.siigo.com/interfaces-movimiento-extracontable/`
- `https://www.siigo.com/siigo-contador/`
- `https://www.siigo.com/prueba-gratis/`
- `C:/Siigo/EXCELSIIGO.exe`
- `C:/Siigo/FECHAACT.CFG`

### Alternativas

- `https://github.com/odoo/odoo`
- `https://www.odoo.com/documentation/19.0/es_419/applications/finance/fiscal_localizations/colombia.html`
- `https://github.com/frappe/erpnext`
- `https://github.com/bvr218/nubicta`
- `https://github.com/javalenciacai/siigo-pyme-mcp` (MIT)
- `https://github.com/javalenciacai/siigo-pyme-excel-skill` (licencia GitHub “Other”)

### Local

- `C:/Users/cjcue/.hermes-shared/IngSW2/workset/README.md`
- `C:/Users/cjcue/.hermes-shared/IngSW2/workset/04_catalogo/CATALOGO SIIGO (Creación líneas grupos y productos).xlsx`
- `C:/Users/cjcue/.hermes-shared/IngSW2/workset/04_catalogo/ot_muestra`
- `C:/Users/cjcue/.hermes-shared/IngSW2/workset/01_ventas/siigo_documentos_electronicos`
- `C:/Users/cjcue/.hermes-shared/IngSW2/analisis-forense`
- `C:/Users/cjcue/.omp-workspace/imsi-verify` (clon viejo; no usar como fuente de 5c/5d)
- `C:/Users/cjcue/.hermes-shared/IngSW2/WeaAngel`
- `C:/Users/cjcue/.hermes-shared/IngSW2/WeaAngel/COPIA JUNIO 02 2026/Backup_121124`

## 10. Conclusión

IMSI tiene la cola 5c, pero no tiene 5d ni un adaptador Siigo funcional. Siigo Pyme 10.1 usa un `.xlsx` de movimiento extracontable con tipos `Z/Y/V`; no hay tipo O.T. y el layout de columnas sigue abierto. Sin licencia no se puede validar una carga real. La salida más honesta es implementar el puerto y el adaptador provisional, probarlo con un mock y documentar la limitación; o cambiar de alcance con ADR si se decide usar Odoo/Nubicta/Alegra.

## 11. Custodia

El workset contiene datos reales de negocio y es local: no debe subirse a GitHub, Moodle ni servicios externos. El transcript de esta sesión también contiene nombres de clientes; no ejecutar empaquetado o publicación de sesiones sin redactarlo antes.
