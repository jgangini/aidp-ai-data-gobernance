> Registro histórico por versión. Sus cifras y estados corresponden al momento descrito; para operar el producto consulta las [guías vigentes](../README.md).

# Releases y handoff a Deploy Studio

Producto `aidp-ai-data-governance`, nombre visible AIDP AI Data Governance, repositorio público `jgangini/aidp-ai-data-gobernance`. Candidata publicada [`v0.3.0-rc.1`](https://github.com/jgangini/aidp-ai-data-gobernance/releases/tag/v0.3.0-rc.1): memoria administrada sobre Autonomous AI Lakehouse 26ai, formulario agrupado y URL canónica nueva. La aceptación OCI permanece detenida por el usuario. El tag se fija al código validado; no se mueven ni reemplazan los tags/assets históricos. Deploy Studio obtiene ese tag resuelto a SHA; no se necesita PAT para descargar código público ni existe VM de portal.

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

La CI no incluye el gate arquitectónico: Sentrux local conserva el fallo frente al baseline vacío, tres funciones complejas heredadas y ninguna nueva frente al extracto congelado. Véase la atribución en [estado de la tarea](../tasks/current.md). La aceptación nativa no se sustituye con esta publicación.

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

El checkpoint público `c9b359f` utilizó `jgangini/aidp-ai-data-gobernance` y conserva project_id/nombre visible. README español ampliado, URLs canónicas actualizadas, modelo en enterprise_ai y grupos genéricos de plataforma/identidad/artefactos del schema 1. La plataforma existente se elige mediante `oci_aidp_platforms`, conservando su patrón y workspace explícito. [Auditoría previa a publicación](publication-audit.md). Esa fase documentó Autonomous pendiente; no se publicó RC4. La candidata 0.3.0 incorpora su implementación según [el contrato de memoria](../agent-memory.md), sin alterar los programas de agentes. Los tags anteriores se conservan.

## Memoria 0.3.0 y controles de aceptación

El SDK de control plane está fijado en 2.189.0. Terraform crea o reutiliza la base exacta sin adoptar la externa; el hook habilita AI con recibo CAS/lease, ETag y work request propios. No se requiere wallet ni se cambia la memoria por SQL directo. El secreto se declara únicamente en preflight/post_apply y el hook usa `DEPLOY_STUDIO_OUTPUT`.

No reutilizar una plataforma READY ajena basándose sólo en ese estado. La primera asociación es evidencia indirecta del request propio y READY; el GET no publica el OCID de la base. Verificaciones posteriores fijan el ETag y se bloquean ante deriva. ACK perdido sin work request verificable queda Pending sin reenvío automático. No se deshabilita AI ni se cambia de base durante mantenimiento o rollback. La continuidad/aislamiento de sesiones sigue pendiente de aceptación nativa autorizada.

El formulario conserva schema 1, los grupos del renderer CTN y sus fuentes reales de plataforma/dominio/administrador/modelo. Tiene trece campos. El parser e input preparation reales aprobaron el perfil 26ai:DW, el secreto opcional para existing READY y la política sin wallet. El validador puro de wallet se ejecutó aislado desde la función CTN: ninguna wallet requerida y una wallet innecesaria rechazada. No se declara importación completa del módulo API local: el entorno Governance carece de FastAPI y el entorno CTN local usa Python 3.11 frente a sintaxis 3.12 de su inventario. La coordinación conserva sus checks del consumidor y retomará Browser después.

Sentrux conserva el baseline vacío fallido. Las responsabilidades nuevas de control plane y sus pruebas cambian la calidad medida de 0.7016 a 0.7005; acoplamiento redondeado 0.07, tres funciones complejas heredadas, cero ciclos/god files. No se agregan funciones complejas ni se resetea la referencia. El gate global sigue sin aprobación; el coste arquitectónico del nuevo controlador queda explícito para revisión.

## Evidencia publicada 0.3.0 RC1

[Release pública e inmutable](https://github.com/jgangini/aidp-ai-data-gobernance/releases/tag/v0.3.0-rc.1), tag anotado resuelto remotamente a `7eec0a8eed107f25a235eb145afa6456508e298c`. La API anónima confirmó acceso público, `immutable=true`, draft false y cuatro assets. Los tres tags 0.2.0 RC1/RC2/RC3 conservan sus hashes; RC4 no se publicó.

- [CI final 42158871228](https://github.com/jgangini/aidp-ai-data-gobernance/actions/runs/42158871228): 1.911 tests Python en 202.04 s, compilación, Terraform fmt/validate y 18 tests con mocks aprobados.
- Postflight `.local/memory-postflight-absence-final.txt`: 1.911 tests en 197.79 s y compilación aprobados; salida global 1 únicamente por Sentrux frente al baseline vacío conservado. Calidad 0.7005, coupling 0.07, tres complejas heredadas, cero ciclos/god files; sin reglas custom. No se declara aceptación global de arquitectura.
- Regresiones focalizadas de memoria/CLI/recibos/artefactos/lifecycle: 149 aprobadas e incluidas en la suite. La aserción antigua de secretos vacíos se corrigió al contrato exacto de ADMIN protegido; no se omitieron controles ni tests. Los intentos anteriores no sustituyen este cierre.
- Wheel independiente: importación fuera del árbol fuente, SDK 2.189.0 y hashes nativos aprobados; los tres archivos de control críticos coinciden byte por byte con el commit. Los programas de agentes y declaraciones del bundle no cambiaron respecto al checkpoint público.
- Parser/extractor real CTN: 132 archivos / 926.841 bytes, dentro de 250 / 10 MiB. Trece campos, grupos, perfil, fuentes y secreto declarados. El resolver completo CTN descargó GitHub con token vacío, repository canónico y SHA fijado, y aprobó el tag publicado. No ejecutó hooks.
- Los cuatro assets se descargaron y sus hashes coinciden con los preparados. Escaneo del candidato: 255 archivos rastreados, sin PEM/tokens detectados; se conservan límites de la auditoría estática previa.
- Graphify no configurado ni inicializado. No se declara arko check ni paridad del runtime nativo. Browser, OCI, APPLY, conversaciones y persistencia de memoria siguen detenidos por el usuario.

| Asset 0.3.0 RC1 | Bytes | SHA-256 |
| --- | ---: | --- |
| `aidp-ai-data-governance-source.zip` | 625190 | `2de7d4aed355656b841c85bc24befead64030357d7d235efb51157c7ea09ed52` |
| `aidp_ai_data_governance-0.3.0-py3-none-any.whl` | 283285 | `45b091d7ccaa5e999ed5e6973aaf24ea2784e76f2b89236d3f7b5608be028c0d` |
| `aidp-governance-release.json` | 886 | `7839fae17334aa4acc4371382787fa5bdd78fc27fa2387f92df57744e900a11c` |
| `SHA256SUMS` | 309 | `688f75abe8a388a41473b309eb24f12ffbbf6128a38331942b997b4225fbbb04` |

El manifiesto de evidencia declara `native_acceptance=paused_by_user` y memoria implementada en control plane, sin aceptación de persistencia nativa. No confundir READY técnico con una sesión/checkpoint real confirmado. ACK incierto sin work request queda Pending y requiere conciliación protegida; una plataforma READY ajena o con ETag cambiado no se adopta. No se deshabilita AI ni se cambia/elimina Autonomous como rollback.

## Candidata 0.3.0 RC2: contrato del runner

Código corregido en `bd91108bf95c8e8a93d4164bb78ad77bb4dca278`, publicado en main. La validación UI coordinada de RC1 falló antes de OCI/APPLY con `Repository preflight returned invalid JSON`. Se reprodujo con el entrypoint real: salida 1, archivo RESULT vacío y JSON sólo en stdout. El CLI confundía los contratos preflight y post-apply.

Preflight ahora consume compartimento string más modo y escribe `DEPLOY_STUDIO_RESULT`; post-apply consume objeto resuelto y escribe `DEPLOY_STUDIO_OUTPUT`. Los errores de contexto también producen JSON. Se exigen archivos explícitos de configuración y clave, sin descubrimiento local; el Signer verifica sus contenidos. Se declaran las seis salidas de operación/estado que el consumidor rechazaba. Los trece campos, programas de agentes y contrato de memoria permanecen iguales.

- [CI 42169061530](https://github.com/jgangini/aidp-ai-data-gobernance/actions/runs/42169061530) aprobada para ese SHA: 1.944 tests Python en 247.30 s, compilación, 18 tests Terraform y 90 tests del runner mínimo en 16.31 s.
- Postflight `.local/runner-contract-postflight-final.txt`: **1.944 tests aprobados en 237.82 s**, compilación aprobada, salida global 1 exclusivamente por Sentrux. Preflight ejecutado antes del cambio, con el mismo fallo contra la referencia vacía conservada.
- Python 3.12/OCI 2.184.1/httpx 0.28.1/Pydantic 2.11.10, más pytest: **90 tests aprobados en 29.61 s**, incluidos 26 de entrypoints y 64 de memoria. No se instalaron requisitos del paquete ni bibliotecas de agentes. La misma ruta pasó en CI Linux.
- Los subprocesos ejecutan parsing, bindings, configuración OCI y Signer reales, con claves efímeras. Cubren preflight new/existing, cinco resultados post-apply, errores de contexto/JSON/credenciales/proveedor y variables de fase cruzadas. Sólo transportes y fronteras de efectos se simulan; red e imports de agentes bloqueados. No es aceptación OCI.
- Las funciones consumidoras CTN capturadas coinciden exactamente con su fuente real; SHA-256 `a5a6765d194d4b62ffdbcbf4c3e3b1804bf10d3a5c84e10b7b03122b8de73c17`. Los cinco resultados pasan el validador con el manifiesto distribuido.
- Terraform fmt/validate y **18 tests con mocks** aprobados. Parser/extractor real CTN: **132 archivos / 928.250 bytes**, dentro de 250 / 10 MiB. Wheel aislado importable sin agentes; CLI idéntico al commit. Escaneo de candidato: 263 archivos, sin claves/tokens detectados. Enlaces locales, trece campos y cinco operaciones documentadas verificados.
- Sentrux completo: calidad **0.7001**, coupling 0.07, **cuatro complejas**, cero ciclos/god files. Sin reglas custom ni reset. Una copia diagnóstica sin el fixture del consumidor CTN conserva tres complejas y 0.7006: la complejidad adicional pertenece a ese fixture legible. Esta atribución no reemplaza el gate final fallido. Graphify no configurado.

Los cuatro assets se construyeron localmente para `v0.3.0-rc.2`. Antes de la aprobación concreta, la revisión automática rechazó crear/publicar el tag por falta de autorización explícita; también rechazó la aprobación reenviada desde el chat coordinador. Esos intentos no crearon tag ni draft y no se intentó eludirlos. El usuario autorizó después explícitamente la publicación; coordinación asumió su ejecución para evitar carreras.

La [prerelease pública e inmutable v0.3.0-rc.2](https://github.com/jgangini/aidp-ai-data-gobernance/releases/tag/v0.3.0-rc.2) está publicada. GitHub confirma `immutable=true`, `draft=false`, `prerelease=true` y los cuatro assets con tamaños y digests iguales a esta tabla. El tag remoto apunta exactamente a `bd91108bf95c8e8a93d4164bb78ad77bb4dca278`. El resolver real CTN, con token vacío y repositorio/SHA esperados, obtuvo el tag y la fuente pública: 132 archivos / 928.250 bytes; CLI idéntico al commit y trece campos preservados. No ejecutó hooks ni OCI. Los tags y assets anteriores permanecen intactos; UI/OCI/APPLY y persistencia nativa continúan bajo coordinación. Las comprobaciones aprobadas no se repitieron; este cierre sólo verificó la publicación y disponibilidad de fuente.

| Asset candidato RC2 | Bytes | SHA-256 |
| --- | ---: | --- |
| `aidp-ai-data-governance-source.zip` | 641665 | `3a98b93db9ceca5f4ab1f9fc44e7a74c7b25ab247a402deeb16a6c314f0c1709` |
| `aidp_ai_data_governance-0.3.0-py3-none-any.whl` | 283553 | `3d730216271f342f6596dd4bffbb6a1a8bddaae68e74f9424758374ee9b23208` |
| `aidp-governance-release.json` | 1252 | `4ac43d1aa29a21a0bafe80acf82208bdb3438d1403292b1c3e123438420fa3ff` |
| `SHA256SUMS` | 312 | `091aced5f575a0cfe3e89fd4aaf157a09743a44e55c32053d55157ab99a9b51b` |

## Candidata 0.3.0 RC3: Resource Manager y selección de servicios

La prueba nativa coordinada de RC2 aprobó Validate y creó compartimento/stack, pero el job Terraform falló antes de crear AIDP: exigía Core 1.9.0 mientras Resource Manager ejecutaba 1.5.7. [Oracle confirma esa CLI](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Reference/terraformversions.htm). El binario oficial 1.5.7, descargado con SHA-256 contrastado contra HashiCorp, reprodujo cuatro errores adicionales de referencias cruzadas en validaciones de variables; esa capacidad se incorporó en [Terraform 1.9](https://github.com/hashicorp/terraform/releases/tag/v1.9.0).

El mínimo es 1.5.7. Las condiciones AIDP/workspace se conservan como preconditions de outputs; la identidad de base existente, como precondition del datasource. La contraseña mantiene su validación propia de complejidad y la base nueva exige que no esté vacía. No se añaden recursos guard, state ni dependencias que difieran las tres postconditions de la base existente a apply. IAM, recursos, propiedad, prevent_destroy y asociación de memoria permanecen iguales.

El formulario elimina el selector de operación y usa `Services mode`, con `Create new AIDP` / `Use existing AIDP`. Conserva `install` por defecto en TF/CLI y los comandos administrativos fuera del formulario, con sus controles de fuente, identidad y recuperación. `Existing workspace` declara la fuente contextual `oci_aidp_workspaces` del AIDP elegido y conserva UUID canónico, required y visible_when existing. La coordinación desarrolla el consumidor CTN; no se afirma que los tests del manifiesto acrediten su inventario OCI. Quedan doce campos.

La etiqueta del modelo es exactamente `Select Model`; fuente y binding no cambian. El primer job Linux de compatibilidad falló al validar proveedores en el harness aislado. Su TMPDIR largo superaba el tamaño habitual de un socket AF_UNIX: el script usa ahora un temporal IPC corto en POSIX, conservando HOME, configuración, clave y copia Terraform aislados. También informa summaries y clasificaciones seguras de `validate -json`, sin detalles del proveedor. Ese candidato intermedio no acredita CI aprobada; la candidata final debe pasar su propio job Linux. Las guardas y los catorce casos no se relajan.

- Preflight ejecutado antes de cambios; mismo fallo frente al baseline vacío preservado.
- Terraform 1.5.7 real: init con mirror de proveedores fijados y lock readonly, validate y **14 casos offline aprobados**. Dos planes create-only comprueban el alcance exacto de recursos (AIDP nuevo/existente, bucket y base nuevos); doce negativos comprueban identidades, contraseña y perfil. Entorno HOME/config aislado, claves sintéticas, red denegada por proxy y cero peticiones observadas. Comando reproducible: `python scripts/check_terraform_compatibility.py --terraform <binario-1.5.7>`. Resolución por PATH también probada.
- La lectura positiva de una base existente requiere OCI: sólo está cubierta por mocks modernos. Sus OCID ausente/inválido se rechazan con 1.5.7 antes de leer el proveedor. No se simula esa lectura como prueba nativa.
- Terraform moderno: fmt/validate y **23 tests con mocks aprobados**. Preflight/post-apply reales sin campo de operación, manifiesto y CLI: **83 tests aprobados**, más comprobación focalizada del selector. No se alteran los programas de agentes ni sus hashes.
- CI separa el job `resource-manager` (1.5.7 real) de `terraform` (mocks modernos), y conserva los jobs Python completo y runner mínimo. El bootstrap añade únicamente hashes de plataforma al lock local sin upgrade; los planes aislados exigen lock readonly y no descargan proveedores.

Los recursos reales existentes y la aceptación UI/OCI siguen bajo coordinación. Este chat no hace APPLY, Docker, Browser, destrucción ni publicación de RC3. Los archivos Graphify locales quedan fuera del commit y assets de release. Los resultados finales de postflight, CI y hashes de esta candidata se agregan al cerrar su preparación.

El formulario final tiene **trece campos**: se agregó el selector `artifacts_existing_bucket_name` y el texto canónico `artifacts_bucket_name` sólo es visible en new. En existing, preflight elige y valida el selector, devuelve el override canónico declarado y post-apply exige coincidencia con modo, contexto y salida Terraform. Ese selector es exclusivamente de formulario/preflight; no se añadió variable Terraform ni fallback legacy. El preparador y validador de overrides reales de CTN aceptaron ambos modos, incluido el override del campo oculto; su filtro de variables fue contrastado con el código del consumidor.

Todos los labels, opciones, etapas y textos de presentación están en inglés; las guías permanecen en español. `Existing Autonomous Database` usa `oci_autonomous_databases`; no se alteran el OCID seleccionado, el perfil 26ai/DW, ADMIN condicional, la política sin wallet ni las comprobaciones de memoria. Verificación focalizada final: **69 tests CLI/manifiesto y 40 entrypoints reales** aprobados. Estos últimos prueban cuatro combinaciones fase/modo de bucket y rechazan selector ausente/inválido, contradicción y cambios de bucket/modo por Terraform antes de acceder a memoria o efectos nativos.

La base `59c53e58312aa142eff4f539151837886a02888c` tiene [CI Linux 42204101467 aprobada](https://github.com/jgangini/aidp-ai-data-gobernance/actions/runs/42204101467), incluida la corrección de temporal IPC y los catorce casos reales 1.5.7. La última parte se entrega para revisión en `codex/deploy-studio-selectors-tf157`, con CI sobre su propio código y sin pushes adicionales a main, tags ni releases. El PR y el manifiesto de la candidata entregan las referencias verificables de ese cierre; la evidencia anterior no sustituye sus checks.

La revisión posterior añade los defaults solicitados: AIDP `new` y Grok 4.7 con ID exacto `xai.grok-4.7`. CTN transmite `model.id` y muestra la versión por separado. Ambos ensambladores rechazaban cualquier ID no OCID; comparten ahora un patrón que conserva el formato anterior y admite únicamente ese ID de servicio verificado, sin gramática genérica de alias ni cambios de compartimento. Se actualizan los hashes de `runtime_source.py`, `governance_source.py` y `documentary_source.py`. Los 57 tests focalizados aprobaron el bundle determinista completo, compilación, hashes y cinco CONFIG con el modelo exacto, treinta rechazos de ID/tipo/compartimento y positivos OCID anteriores. No hubo inferencia ni prueba de calidad. El preparador real de CTN también resolvió `new` y `xai.grok-4.7` cuando el formulario omitió ambos valores. El [PR #1](https://github.com/jgangini/aidp-ai-data-gobernance/pull/1) y los assets deben apuntar al nuevo SHA validado, sin reutilizar el paquete previo a estos defaults.
