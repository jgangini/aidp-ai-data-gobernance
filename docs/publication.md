# Publicación del repositorio

El usuario autorizó el nombre exacto `jgangini/aidp-ai-data-gobernance` (con b), visibilidad pública y README del proyecto en español. El identificador técnico sigue siendo `aidp-ai-data-governance`; el nombre visible es AIDP AI Data Governance. El directorio local no se renombra.

## Auditoría previa

Una revisión independiente de sólo lectura examinó el snapshot `cc591e7`: 248 archivos rastreados y 275 blobs únicos alcanzables desde ocho commits y cinco refs locales, con 2.274.231 bytes históricos. La consulta remota confirmó main y los tres tags conocidos, sin otra rama o tag fuera de ese alcance.

No se encontraron secretos confirmados ni archivos históricos de `.oci`, `.local`, state Terraform, wallets, PEM privados, tokens conocidos de proveedores/GitHub ni JWT. Las coincidencias revisadas fueron fixtures de rechazo/redacción, prefijos OCID de prueba y un token de reintento construido en ejecución. No se imprimieron valores ni se abrieron credenciales locales.

Los commits conservan el correo nominal de autor/committer. Es metadata de autoría que queda expuesta al hacer público el historial; no se reescribió porque deben preservarse commits y tags anteriores.

La auditoría es estática: no comprueba validez de credenciales online ni puede garantizar ausencia absoluta de secretos desconocidos. Los assets de las tres releases anteriores corresponden a los ZIP/wheel y manifiestos ya verificados por hashes; se confirmó su metadata remota e inmutabilidad. Esta revisión no operó OCI, Browser ni Docker.

## URLs e identidad

Se actualizan el remote, `presentation.href`, los enlaces de documentación y los URLs de metadata del paquete al repositorio canónico. El workflow usa `actions/checkout` sobre el repositorio actual y no contiene un nombre GitHub codificado. `provenance.json` conserva la identidad del repositorio fuente congelado.

Los tags, assets y manifiestos de releases anteriores no se alteran: sus URLs originales permanecen como evidencia histórica y GitHub mantiene las redirecciones del rename. La nueva release se construye desde su commit exacto y declara la URL canónica nueva. El rename no relaja el vínculo source/ref/SHA de recibos existentes; no migrar una operación pendiente cambiándole su identidad de fuente.

## Alcance de memoria

El nombre público y el README se completaron en `c9b359f`. La continuación incorpora aprovisionamiento y habilitación de memoria con SDK compatible, manteniendo separada la aceptación nativa. El [contrato de memoria](agent-memory.md) registra el runtime real, los campos consumidos y la falta de un readback directo del OCID asociado. No hay campos ni recursos Autonomous decorativos. Las pruebas de despliegue permanecen detenidas por el usuario.

La API confirmó `private=false` y `visibility=public`; una lectura anónima sin token también aprobó. El rename conservó la inmutabilidad de releases y los hashes de los tags previos.
