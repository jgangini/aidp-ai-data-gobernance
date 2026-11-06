# Releases y handoff a Deploy Studio

Producto `aidp-ai-data-governance`, nombre visible AIDP AI Data Governance, repositorio público `jgangini/aidp-ai-data-gobernance`. Candidata `v0.3.0-rc.1`: memoria administrada sobre Autonomous AI Lakehouse 26ai, formulario agrupado y URL canónica nueva. La aceptación OCI permanece detenida por el usuario. El tag se fija al código validado; no se mueven ni reemplazan los tags/assets históricos. Deploy Studio obtiene ese tag resuelto a SHA; no se necesita PAT para descargar código público ni existe VM de portal.

## Conjunto exacto de assets

- `aidp-ai-data-governance-source.zip`: `git archive` del commit exacto, con raíz única `source/`; contiene Terraform, hooks, requirements y fuentes AIDP.
- `aidp_ai_data_governance-0.3.0-py3-none-any.whl`: paquete importable para distribución y verificación independiente.
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
| `identity_domain_id` | seleccionar dominio ACTIVE de la lista; valor guardado: OCID del dominio |
| `admin_user_ocid` | OCID estable del candidato activo listado por Deploy Studio; el hook asigna/verifica el rol tras bootstrap |
| `artifacts_mode` | `new` o `existing` según la selección explícita y validada |
| `artifacts_bucket_name` | nombre único acordado del bucket de artefactos; no un bucket de datos medallion |
| `model_id` | modelo OCI existente elegido en el selector, autorizado para el destino |
| `autonomous_database_mode` | `new` o `existing`, base de memoria administrada |
| `autonomous_database_version` | perfil nuevo `26ai:DW`; el runner expande versión/workload |
| `existing_autonomous_database_ocid` | OCID exacto de la Lakehouse AVAILABLE/26ai/DW, sólo en existing |
| `autonomous_database_admin_password` | secreto protegido para crear o habilitar memoria; vacío permitido al verificar una asociación propia existing ya READY |

El runner resuelve tenancy, compartment, region, `objectstorage_namespace`, `deployment_suffix` y credenciales; preflight devuelve `home_region`. Con new, la plataforma se llama `aidp-governance-<deployment_suffix>` y su workspace `governance-<deployment_suffix>`.

Después del éxito, utilizar **el resultado final del post-apply**: `ai_data_platform_ocid` identifica el único AIDP creado y `workspace_key` es su UUID verificado. El output Terraform `workspace_key` de new es inicialmente vacío: no pasarlo como selección existing a los otros módulos. Conservar `identity_domain_id` y `admin_user_ocid` verificados. Market y GodEye deben recibir esos IDs bajo su modo existing; no crear otra plataforma ni copiar estado entre stacks.

Para reanudar Governance: mismo deployment_id, tag/SHA, identidad y contexto. Para update/redeploy/rollback: misma instalación/stack/destino, contexto de la operación autorizado y selección correspondiente de `governance_operation`; el recibo verifica ownership, fuente y revisión. No aplicar un plan que cree/reemplace otra plataforma para simular un update.

## Gates y límites

Una candidata publicada no implica aceptación de conversaciones ni de ejecución/schedule real. El instalador puede devolver código 3 mientras una fase nativa está pendiente: continuar la misma operación, no crear otro deployment o recurso para forzar éxito. Una recuperación correcta de un update fallido devuelve código 1 y `update_failed_restored`; conservar el fallo original.

El rollback cubre artefactos propios y refresh, no datos. Se bloquea ante esquema/storage/modelo incompatible, blobs corruptos, identidad ajena, una nueva ejecución previa al restore o falta de evidencia. Revocaciones no se restauran al Resume. No hay borrado, transferencia de state ni publicación consultiva PROD. Sentrux conserva su referencia vacía fallida, con solo tres funciones complejas heredadas y ninguna nueva: no se declara gate global aprobado.

## Evidencia publicada RC1

- Commit exacto del tag anotado: `168273bbb8c4f143602aecea71a1d8552a995acf`; verificado por resolución remota del tag. No moverlo al cierre documental posterior.
- [CI 42146959451](https://github.com/jgangini/aidp-ai-data-gobernance/actions/runs/42146959451): 1.836 tests Python en 246.80 s, compilación y cinco tests Terraform aprobados.
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

[Release privada e inmutable v0.2.0-rc.2](https://github.com/jgangini/aidp-ai-data-gobernance/releases/tag/v0.2.0-rc.2), tag remoto resuelto a `851d83757b15fd4938a366738e2fd606a8c26b5b`. GitHub confirmó `isImmutable=true`, `isDraft=false`, `isPrerelease=true`; los cuatro assets descargados coinciden con sus hashes. No se modificó RC1.

[CI 42149734792](https://github.com/jgangini/aidp-ai-data-gobernance/actions/runs/42149734792) aprobó 1.836 tests Python en 192.39 s, compilación y cinco tests Terraform. Postflight local: 1.836 tests en 215.10 s y compilación aprobados; termina con error únicamente por Sentrux, igual a RC1 (calidad 0.7016, tres complejas, cero ciclos/god files). Baseline conservado; sin reglas custom. El parser real aprobó 129 archivos / 889.181 bytes, título exacto, PNG existente y texto alternativo. La revisión UI/OCI sigue pendiente de coordinación, sin Browser/Docker/OCI operados por este chat.

| Asset RC2 | Bytes | SHA-256 |
| --- | ---: | --- |
| `aidp-ai-data-governance-source.zip` | 596891 | `40c8d6763082585f536ae82bc39d0b8d873efa8f5daf0daf678d4e8b9967c28d` |
| `aidp_ai_data_governance-0.2.0-py3-none-any.whl` | 277589 | `c9597470a59b9c8beaeb35a4b3a49575e15bfa8a176568e046532b33a4b98121` |
| `aidp-governance-release.json` | 793 | `a74ef920a11f83acc26ac257f354de531b098ac1a49ddd90b6c50310487e79e8` |
| `SHA256SUMS` | 309 | `b3d248941a983153b0b907ecbdb428058f0c8096944ba76097f706c30f668dd3` |

## RC3: selector Identity Domain

`v0.2.0-rc.3` cambia únicamente el campo `identity_domain_id` de texto a select con `options_source: oci_identity_domains`, obligatorio y con el patrón de OCID previo. La coordinación implementa el consumidor CTN (dominios ACTIVE, región home, labels nombre/compartimento); Governance conserva las verificaciones de identidad nativas. Se mantienen la ficha AIDP AI Data Governance, su PNG, hooks, Terraform y wheel 0.2.0. RC1 y RC2 permanecen inmutables. No se consultó OCI ni se operaron Browser/Docker compartidos.

### Publicación y verificación RC3

[Release privada e inmutable v0.2.0-rc.3](https://github.com/jgangini/aidp-ai-data-gobernance/releases/tag/v0.2.0-rc.3), tag remoto resuelto a `d46a66d9972c63bceb70ce5b72e258657cdcbfc3`. GitHub confirmó `isImmutable=true`, `isDraft=false`, `isPrerelease=true`; los cuatro assets descargados coinciden con sus hashes. No se modificaron RC1/RC2.

[CI 42151723191](https://github.com/jgangini/aidp-ai-data-gobernance/actions/runs/42151723191) aprobó 1.836 tests Python en 274.77 s, compilación y cinco tests Terraform. Postflight local: 1.836 tests en 218.38 s y compilación aprobados; mismo fallo Sentrux heredado (calidad 0.7016, tres complejas, cero ciclos/god files; baseline conservado y sin reglas custom). Parser real CTN actualizado aprobado sobre el ZIP publicado: 129 archivos / 889.225 bytes; `select`, source, required y patrón correctos, nombre/PNG conservados. Enumeración real de dominios y aceptación UI/OCI bajo coordinación; no se operaron recursos compartidos desde este chat.

| Asset RC3 | Bytes | SHA-256 |
| --- | ---: | --- |
| `aidp-ai-data-governance-source.zip` | 598046 | `0a172c4133d15e4d5b67728df65b5e88d20023ecc671ac1763caab2a9fe9d309` |
| `aidp_ai_data_governance-0.2.0-py3-none-any.whl` | 277589 | `c9597470a59b9c8beaeb35a4b3a49575e15bfa8a176568e046532b33a4b98121` |
| `aidp-governance-release.json` | 793 | `957e11a55182eaaa27755451cbc84ad02b7e038a1697b28fcc4d7500622cb8e5` |
| `SHA256SUMS` | 309 | `f002504166c46127f0266204e8f1bc1013896bcada9912c8b938d8d53f14f7cd` |

## RC4: nombre canónico público y formulario agrupado

El checkpoint público `c9b359f` utilizó `jgangini/aidp-ai-data-gobernance` y conserva project_id/nombre visible. README español ampliado, URLs canónicas actualizadas, modelo en enterprise_ai y grupos genéricos de plataforma/identidad/artefactos del schema 1. La plataforma existente se elige mediante `oci_aidp_platforms`, conservando su patrón y workspace explícito. [Auditoría previa a publicación](publication.md). Esa fase documentó Autonomous pendiente; no se publicó RC4. La candidata 0.3.0 incorpora su implementación según [el contrato de memoria](agent-memory.md), sin alterar los programas de agentes. Los tags anteriores se conservan.

## Memoria 0.3.0 y controles de aceptación

El SDK de control plane está fijado en 2.189.0. Terraform crea o reutiliza la base exacta sin adoptar la externa; el hook habilita AI con recibo CAS/lease, ETag y work request propios. No se requiere wallet ni se cambia la memoria por SQL directo. El secreto se declara únicamente en preflight/post_apply y el hook usa `DEPLOY_STUDIO_OUTPUT`.

No reutilizar una plataforma READY ajena basándose sólo en ese estado. La primera asociación es evidencia indirecta del request propio y READY; el GET no publica el OCID de la base. Verificaciones posteriores fijan el ETag y se bloquean ante deriva. ACK perdido sin work request verificable queda Pending sin reenvío automático. No se deshabilita AI ni se cambia de base durante mantenimiento o rollback. La continuidad/aislamiento de sesiones sigue pendiente de aceptación nativa autorizada.

El formulario conserva schema 1, los grupos del renderer CTN y sus fuentes reales de plataforma/dominio/administrador/modelo. Tiene trece campos. El parser e input preparation reales aprobaron el perfil 26ai:DW, el secreto opcional para existing READY y la política sin wallet. El validador puro de wallet se ejecutó aislado desde la función CTN: ninguna wallet requerida y una wallet innecesaria rechazada. No se declara importación completa del módulo API local: el entorno Governance carece de FastAPI y el entorno CTN local usa Python 3.11 frente a sintaxis 3.12 de su inventario. La coordinación conserva sus checks del consumidor y retomará Browser después.

Sentrux conserva el baseline vacío fallido. Las responsabilidades nuevas de control plane y sus pruebas cambian la calidad medida de 0.7016 a 0.7005; acoplamiento redondeado 0.07, tres funciones complejas heredadas, cero ciclos/god files. No se agregan funciones complejas ni se resetea la referencia. El gate global sigue sin aprobación; el coste arquitectónico del nuevo controlador queda explícito para revisión.
