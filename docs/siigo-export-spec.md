# Exportación IMSI → Siigo: verificación corregida

Fecha: 2026-11-28
Auditorías: `RemoteExportAudit` + `Siigo10Audit`.

## Veredicto

- En el remoto `feat/first-release`, SHA **`410ef36`**, la cola exporta **Órdenes de Trabajo (O.T.)**, no cotizaciones.
- **5c está implementado; 5d no.** El archivo y el paso a “Registrada en Siigo” siguen pendientes.
- Siigo Pyme 10.1 **no tiene un tipo “O.T.”**. Su vía documentada de importación es **Interfaces → Importaciones desde Excel → Movimiento extracontable**, con un **.xlsx generado por la propia instalación**, tipos `Z` (pedido), `Y` (orden de compra) o `V` (cotización).
- El layout de columnas de IMSI sigue **sin definir**; el repo lo declara ítem abierto bloqueante.
- Un CSV propio **no entra** por la vía documentada. La salida tendría que ser el `.xlsx` del modelo extracontable, con encabezados en la fila 5 y columnas inamovibles.

## Qué exporta IMSI

La O.T. (`OT-YYYYMMDD-NNNNN`) con la cotización de origen como referencia. Campos definidos en el código remoto:

| Campo | Estado |
|---|---|
| `number` (O.T.) | definido |
| `quotation_number` | definido como referencia |
| `created_at` | definido |
| `customer_name`, `customer_tax_id` | definido |
| `items`: `product_code`, `description`, `unit_of_measure`, `quantity` | definido |
| `agreed_delivery_date` | definido |
| precios, IVA, anticipo, totales | **no existen en la O.T. de IMSI** |

La O.T. real de la empresa sí lleva precios, IVA y retención; eso choca con la decisión de diseño “O.T. sin precios”.

## Qué necesita Siigo 10.1

Fuente oficial: <https://siigopyme2.portaldeclientes.siigo.com/interfaces-movimiento-extracontable/>

- Modelo `.xlsx` generado desde la instalación, según empresa/módulos.
- Fila 5 con los nombres de columna; no cambiar fuente, filas de encabezado, orden ni nombres.
- Obligatorios: **TIPO DE DOCUMENTO**, **CÓDIGO DOCUMENTO**, **NÚMERO DE DOCUMENTO**.
- Grupos opcionales: tercero, producto, cantidad, valores, impuestos, etc.
- No hay tipo O.T.; hay que mapear a `V` cotización o `Z` pedido.
- `ExcelSIIGO.exe` expone `GETEXT`/`PUSHEXT`; usa `.xlsx`, no un CSV propio.

## Contradicciones

1. **Diseño vs código:** el handoff/README viejo habla a veces de cotizaciones; el remoto `410ef36` dice O.T.
2. **CSV/TXT vs .xlsx:** el repo pide “flat file CSV/TXT”; Siigo 10.1 usa .xlsx.
3. **Sin precios vs importación útil:** la O.T. de IMSI no tiene valores; el modelo extracontable tiene columnas de valor.
4. **Numeración:** `OT-YYYYMMDD-NNNNN` es texto; la empresa usa consecutivos numéricos de 4 dígitos.
5. **Tipo de documento:** no existe “O.T.” en Siigo; hay que decidir `V` o `Z`.

## Alternativas legales sin licencia

No se debe usar una copia pirata: es delito y riesgo de malware. Opciones:

1. **Pedir demo/licencia educativa a Siigo** y generar el modelo real desde esa instalación. Es la única forma de validar columnas y una carga de prueba.
2. **Implementar un `SiigoExtracontableFormatter`** que produzca el `.xlsx` con el modelo oficial; dejar el layout en una pieza reemplazable y probar con un workbook sintético. Sin licencia no se puede validar la carga real.
3. **Usar los wrappers existentes** `javalenciacai/siigo-pyme-mcp` (MIT) o `siigo-pyme-excel-skill` (licencia GitHub “Other”) solo si hay Siigo Pyme + Excel instalados; no reemplazan a Siigo.
4. **Nubicta** (`bvr218/nubicta`, MIT): ERP contable colombiano con DIAN; alternativa open source, no un clon de Siigo y requiere migración.
5. **Odoo + localización colombiana / Facturalam**: más pesado, pero legal y con facturación DIAN.
6. **Mock Siigo**: entregar el adaptador y un archivo de ejemplo marcado como provisional; documentar que la carga real queda pendiente de plantilla/licencia.

## Planes gratuitos de Siigo

- **Siigo Contador gratis:** producto en la nube, 1 empresa, contabilidad/impuestos/estados financieros. La página oficial no documenta importación extracontable de Pyme. **No consta** que sirva para el flujo O.T. → Pyme 10.1.
- **Facturación Electrónica gratis/prueba:** producto en la nube con límites de documentos/clientes. No consta que incluya la importación Excel/extracontable de Pyme.
- **Siigo Pyme 10.1:** único producto con la vía documentada de **movimiento extracontable** y `EXCELSIIGO.exe`; requiere licencia.

No presentar los planes gratuitos como sustituto de Pyme 10.1. Solo son alternativas para facturación/contabilidad en la nube, no para validar el layout de Pyme.

## Cambio de alcance

Sustituir Siigo por un mock, CSV o Nubicta **es un cambio de alcance**, no un simple cambio de README. Requiere:

- ADR que registre la decisión, el motivo (sin licencia), el adaptador afectado y el criterio de aceptación.
- Aceptación explícita del profesor/cliente.
- Dejar claro que el adaptador Siigo queda implementado/probado contra contrato, pero la carga real no está validada.

## Sobre “MDP”

No encontré un término oficial de Siigo llamado “MDP”. Las búsquedas devuelven MDP de transporte o protocolos, no Siigo. Si te refieres al **modelo de datos** o al **módulo de documentos**, hay que precisar el nombre; no lo invento.

## Evidencias

- Remoto: `https://api.github.com/repos/Testigos-de-Meluk/Integrated-Management-System-for-School-Industries/branches/feat/first-release` → `410ef36`.
- `Workshops/Corrections/README.md` §4.1 FR-02-16/17/18; §7 ítem 2; NFR-06-02.
- `backend/modules/accounting_export/domain/queue_entry.py`; `application/export_queue_service.py`.
- Siigo: página oficial de movimiento extracontable; `C:/Siigo/EXCELSIIGO.exe`; `C:/Siigo/FECHAACT.CFG`.
- GitHub: `bvr218/nubicta`, `javalenciacai/siigo-pyme-mcp`, `jdlar1/siigo-mcp`.
