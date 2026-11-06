# Distribución y releases

El producto se distribuye desde el [repositorio público](https://github.com/jgangini/aidp-ai-data-gobernance) y sus [releases](https://github.com/jgangini/aidp-ai-data-gobernance/releases). El identificador técnico es `aidp-ai-data-governance`, el paquete Python `ai_data_governance` y el comando instalado `aidp-governance`.

## Seleccionar una versión

Deploy Studio resuelve un tag a su commit y obtiene el código de esa revisión. Usa una release inmutable y conserva el tag/SHA registrado al reanudar una operación. El repositorio público no requiere PAT para su descarga.

Una release candidata no es una instalación OCI aceptada. Revisa sus límites antes de aplicar; la publicación consultiva PROD no está implementada. Las instrucciones de instalación y parámetros están en [Deploy Studio](deploy-studio.md).

## Assets

| Archivo | Contenido |
| --- | --- |
| `aidp-ai-data-governance-source.zip` | Archivo del commit exacto con raíz `source/`: Terraform, hooks, requirements y fuentes AIDP. |
| `aidp_ai_data_governance-<versión>-py3-none-any.whl` | Paquete Python importable, con recursos y fuentes distribuidas. |
| `aidp-governance-release.json` | Evidencia del producto: repositorio, tag, commit, tamaños y SHA-256 de ZIP/wheel. |
| `SHA256SUMS` | Hashes del ZIP, wheel y manifiesto de evidencia. |

El manifiesto de evidencia no sustituye `terraform/deploy-studio.json` ni amplía su schema. No se incluyen credenciales, state, `.oci`, recibos reales o logs privados.

Comprueba los hashes contra el manifiesto y `SHA256SUMS` antes de usar un asset descargado. Deploy Studio selecciona la clausura de Terraform/hooks y sus `include_paths`; el wheel permite verificar el paquete por separado, pero instalarlo con pip no aprovisiona recursos OCI.

## Publicar una candidata

La publicación debe partir de un commit validado y de assets construidos desde esa revisión. Mantén habilitada la inmutabilidad, sube todos los assets al draft y publica después. Una corrección usa otro tag; no se mueven tags ni se reemplazan assets de una release inmutable. [Contrato GitHub](https://docs.github.com/en/rest/repos/repos#enable-immutable-releases).

Para cambios sólo documentales, publica la documentación en main sin volver a generar binarios ni alterar releases existentes. Los usuarios de un tag siguen viendo sus fuentes congeladas; main describe el funcionamiento vigente.

## Compatibilidad y aceptación

Resume exige la fuente original. Una actualización usa el contexto autorizado de la misma instalación/state y respeta sus bindings; no cambia recursos de destino para aparentar un update. El mantenimiento de artefactos no cambia la base de memoria.

`TEST_PENDING`, READY/ACTIVE, una CI aprobada o una release publicada no demuestran aceptación funcional, persistencia de sesiones o ejecución real del workflow. Consulta [operación](contracts.md) y [memoria](agent-memory.md) para las guardas que deben conservarse.

Los [hashes y resultados por versión](history/release-evidence.md), la [auditoría de publicación](history/publication-audit.md) y la [procedencia](history/README.md) son registros separados; no sustituyen estas instrucciones de uso.
