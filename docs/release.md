# Release privada y handoff a Deploy Studio

Producto `aidp-ai-data-governance`. Release de prueba vigente [`v0.2.0-rc.2`](https://github.com/jgangini/aidp-ai_data_governance/releases/tag/v0.2.0-rc.2): implementación 0.2.0 con recuperación de artefactos; aceptación OCI todavía pendiente. La visibilidad se conserva privada y el tag se congela en el SHA probado por CI. Deploy Studio obtiene el código de ese tag resuelto a SHA; el módulo no descarga assets con PAT ni tiene VM de portal.

## Conjunto exacto de assets

- `aidp-ai-data-governance-source.zip`: `git archive` del commit exacto, con raíz única `source/`; contiene Terraform, hooks, requirements y fuentes AIDP.
- `aidp_ai_data_governance-0.2.0-py3-none-any.whl`: paquete importable para distribución y verificación independiente.
- `aidp-governance-release.json`: schema 1 de evidencia del producto, repositorio/tag/commit y SHA-256/tamaño de los dos payloads. No sustituye `terraform/deploy-studio.json` ni agrega campos a su schema 1.
- `SHA256SUMS`: hashes de ZIP, wheel y manifiesto de evidencia. No se incluyen `.oci`, state, recibos reales, logs privados ni claves.

La inmutabilidad debe estar habilitada antes de publicar. Se suben todos los assets antes de publicar el draft; después no se reemplaza un asset ni se mueve el tag. Las correcciones posteriores usan otro tag. [API oficial de inmutabilidad](https://docs.github.com/en/rest/repos/repos#enable-immutable-releases).

## Parámetros para la prueba de un AIDP compartido

La coordinación es el único dueño del Browser, colas y mutaciones OCI. Seleccionar el usuario en Deploy Studio no cambia el signer del operador.

| Campo Governance | Primera instalación |
| --- | --- |
| `governance_operation` | `install` |
| `aidp_mode` | `new` |
| `existing_ai_data_platform_ocid` | vacío/no visible |
| `existing_workspace_key` | vacío/no visible |
| `identity_domain_id` | OCID exacto del dominio seleccionado |
| `admin_user_ocid` | OCID estable del candidato activo listado por Deploy Studio; el hook asigna/verifica el rol tras bootstrap |
| `artifacts_mode` | `new` o `existing` según la selección explícita y validada |
| `artifacts_bucket_name` | nombre único acordado del bucket de artefactos; no un bucket de datos medallion |
| `model_id` | modelo OCI existente elegido en el selector, autorizado para el destino |

El runner resuelve tenancy, compartment, region, `objectstorage_namespace`, `deployment_suffix` y credenciales; preflight devuelve `home_region`. Con new, la plataforma se llama `aidp-governance-<deployment_suffix>` y su workspace `governance-<deployment_suffix>`.

Después del éxito, utilizar **el resultado final del post-apply**: `ai_data_platform_ocid` identifica el único AIDP creado y `workspace_key` es su UUID verificado. El output Terraform `workspace_key` de new es inicialmente vacío: no pasarlo como selección existing a los otros módulos. Conservar `identity_domain_id` y `admin_user_ocid` verificados. Market y GodEye deben recibir esos IDs bajo su modo existing; no crear otra plataforma ni copiar estado entre stacks.

Para reanudar Governance: mismo deployment_id, tag/SHA, identidad y contexto. Para update/redeploy/rollback: misma instalación/stack/destino, contexto de la operación autorizado y selección correspondiente de `governance_operation`; el recibo verifica ownership, fuente y revisión. No aplicar un plan que cree/reemplace otra plataforma para simular un update.

## Gates y límites

Release privada de prueba no implica aceptación de conversaciones ni de ejecución/schedule real. El instalador puede devolver código 3 mientras una fase nativa está pendiente: continuar la misma operación, no crear otro deployment o recurso para forzar éxito. Una recuperación correcta de un update fallido devuelve código 1 y `update_failed_restored`; conservar el fallo original.

El rollback cubre artefactos propios y refresh, no datos. Se bloquea ante esquema/storage/modelo incompatible, blobs corruptos, identidad ajena, una nueva ejecución previa al restore o falta de evidencia. Revocaciones no se restauran al Resume. No hay borrado, transferencia de state ni publicación consultiva PROD. Sentrux conserva su referencia vacía fallida, con solo tres funciones complejas heredadas y ninguna nueva: no se declara gate global aprobado.

## Evidencia publicada RC1

- Commit exacto del tag anotado: `168273bbb8c4f143602aecea71a1d8552a995acf`; verificado por resolución remota del tag. No moverlo al cierre documental posterior.
- [CI 42146959451](https://github.com/jgangini/aidp-ai_data_governance/actions/runs/42146959451): 1.836 tests Python en 246.80 s, compilación y cinco tests Terraform aprobados.
- GitHub confirmó `isImmutable=true`, `isDraft=false`, `isPrerelease=true`; repositorio privado después de publicar.
- Los cuatro assets se descargaron de GitHub y sus bytes coinciden con los preparados. ZIP: 248 archivos de fuente; consumidor real seleccionó 129 archivos / 888.818 bytes, nueve campos y cinco operaciones dentro de 250 archivos / 10 MiB.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `aidp-ai-data-governance-source.zip` | 594959 | `0b82339353da6fc002b3661e9157e20d38524e37abe44bd75d848a8178187b87` |
| `aidp_ai_data_governance-0.2.0-py3-none-any.whl` | 277589 | `c9597470a59b9c8beaeb35a4b3a49575e15bfa8a176568e046532b33a4b98121` |
| `aidp-governance-release.json` | 793 | `809d02401b2cf1e299e4f4d76644d78d912c855c915064ee8f5c02487f6851ce` |
| `SHA256SUMS` | 309 | `7467359073e9a26af683aed078c485d05f0e5468c9dd09981bc734aac8f7b75e` |

La CI no incluye el gate arquitectónico: Sentrux local conserva el fallo frente al baseline vacío, tres funciones complejas heredadas y ninguna nueva frente al extracto congelado. Véase la atribución en [estado de la tarea](tasks/current.md). La aceptación nativa no se sustituye con esta publicación.

## RC2: ficha de presentación

`v0.2.0-rc.2` incorpora el nombre visible exacto «AIDP AI Data Governance», la descripción de los dos agentes, las dieciocho tablas y las cuatro tareas, y la imagen de plataforma ya disponible en CTN. Ruta: `/assets/oci-aidp-cloud-migration-lab.png`; usa el mismo contrato de imagen pública local que Starter Kits, sin URL privada de GitHub ni token en el navegador. El asset fue inspeccionado y el coordinador confirmó esa ruta. Es ilustración de plataforma compartida, no evidencia del despliegue.

El runtime Python, Terraform y los hooks de RC1 no cambian. El wheel 0.2.0 se conserva byte por byte; el ZIP y el manifiesto de evidencia identifican el nuevo commit. La aceptación UI/OCI sigue a cargo de coordinación. RC1 permanece inmutable.

### Publicación y verificación RC2

[Release privada e inmutable v0.2.0-rc.2](https://github.com/jgangini/aidp-ai_data_governance/releases/tag/v0.2.0-rc.2), tag remoto resuelto a `851d83757b15fd4938a366738e2fd606a8c26b5b`. GitHub confirmó `isImmutable=true`, `isDraft=false`, `isPrerelease=true`; los cuatro assets descargados coinciden con sus hashes. No se modificó RC1.

[CI 42149734792](https://github.com/jgangini/aidp-ai_data_governance/actions/runs/42149734792) aprobó 1.836 tests Python en 192.39 s, compilación y cinco tests Terraform. Postflight local: 1.836 tests en 215.10 s y compilación aprobados; termina con error únicamente por Sentrux, igual a RC1 (calidad 0.7016, tres complejas, cero ciclos/god files). Baseline conservado; sin reglas custom. El parser real aprobó 129 archivos / 889.181 bytes, título exacto, PNG existente y texto alternativo. La revisión UI/OCI sigue pendiente de coordinación, sin Browser/Docker/OCI operados por este chat.

| Asset RC2 | Bytes | SHA-256 |
| --- | ---: | --- |
| `aidp-ai-data-governance-source.zip` | 596891 | `40c8d6763082585f536ae82bc39d0b8d873efa8f5daf0daf678d4e8b9967c28d` |
| `aidp_ai_data_governance-0.2.0-py3-none-any.whl` | 277589 | `c9597470a59b9c8beaeb35a4b3a49575e15bfa8a176568e046532b33a4b98121` |
| `aidp-governance-release.json` | 793 | `a74ef920a11f83acc26ac257f354de531b098ac1a49ddd90b6c50310487e79e8` |
| `SHA256SUMS` | 309 | `b3d248941a983153b0b907ecbdb428058f0c8096944ba76097f706c30f668dd3` |
