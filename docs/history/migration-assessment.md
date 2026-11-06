> Registro histórico por versión. Sus cifras y estados corresponden al momento descrito; para operar el producto consulta las [guías vigentes](../README.md).

# Diagnóstico de separación de AI Data Governance

Fecha: 2026-11-05 (America/Lima). Registro del diagnóstico inicial. La implementación local fue autorizada después; el estado vigente y las pruebas del candidato están en [docs/tasks/current.md](../tasks/current.md), y el contrato implementado en [docs/contracts.md](../contracts.md). Este inventario conserva la evidencia del corte, no afirma instalación cloud ni publicación de release.

Governance se entrega como paquete Python con CLI/hooks y artefactos AIDP. Deploy Studio instala, reanuda y actualiza el producto y permite seleccionar allí al administrador elegible. Governance no tendrá frontend, diálogo propio, login local, servidor HTTP de portal, VM administrativa ni imagen de portal.

## Fuente, destino y alcance

- Fuente de solo lectura: `D:/dev/codex-oci-ai-data-platform-workbench-starter-kits`, HEAD verificado `3c82617fd298933995e954955841007253cc0985` (v4.0.11 indicada por coordinación). El estado Git inicial no mostró cambios.
- Destino: `D:/dev/codex-aidp-ai_data_governance`. Existía vacío, sin Git, remoto configurado ni `.oci`. Repositorio solicitado: `jgangini/aidp-ai_data_governance`. La consulta autenticada `gh api` realizada por coordinación devolvió HTTP 404: ausente o sin acceso; no demuestra por sí sola inexistencia. Este chat no repitió la consulta, inicializó ni clonó.
- En la lectura final del destino apareció `.oci`, ausente al inicio; esta tarea no la creó, abrió ni modificó. No se evaluaron sus credenciales ni su validez. Revalidar preparación e identidad antes de cualquier operación futura.
- Autoridad: solicitud del coordinador, `AGENTS.md`, `docs/contracts.md`, `docs/development.md` y `docs/modules/ai-data-governance.md` de la fuente. No existe `.codex/AGENTS.md` en la fuente. El plan común `docs/module-repository-separation.md`, disponible después de la inspección inicial, fue leído y es el contrato de coordinación al que se subordina este inventario; no fue modificado por este chat.
- Se leyeron Arko, AIDP Agent Flow LangGraph y sus contratos de factory/paridad, y las guías OCI Workbench Source Intake y Workbench Deploy. Source Intake no se ejecuta: esta separación parte de código estable, no de `.source/`. No se ejecutaron comandos OCI ni inicializadores.
- El Graphify existente está basado en `2adb89a4`, anterior a la fuente congelada: se consultaron informe e índice como orientación, sin tomar sus relaciones como prueba de vigencia. Semble se usó una vez con las exclusiones existentes; el código congelado es la evidencia primaria.

Las rutas de evidencia que siguen son relativas a la fuente congelada. El inventario al final identifica el conjunto candidato completo, sin copiar fuentes ni datos privados.

## Comportamiento confirmado por código y descriptores

El ID canónico es `ai_data_governance`. `aidp/manifest.json` del módulo declara `deployment_stage=TEST`, `native_acceptance=pending` y publicación en `/Workspace/.artifact/ai_data_governance`. `default` es alias local del workspace seleccionado, no una orden de crear otro workspace. Los recursos se vinculan por identidad exacta; nombres coincidentes no autorizan adopción.

| Recurso | Contrato confirmado |
| --- | --- |
| Agente consultivo | `ai_data_governance`, entrada `agents/governance/governance_agent.py`, stage TEST, aceptación TEST_PENDING. |
| Agente documental | `ai_data_governance_sync_master_catalog`, entrada `agents/documentation/documentation_agent.py`, stage WORKFLOW_WORKER, aceptación TEST_PENDING. No equivale a publicar el consultivo en PROD. |
| AI Compute | `aidp_data_governance_agent_compute`, propiedad módulo; descriptor inicial 1 OCPU, 16 GiB, una réplica. No es dimensionamiento medido. |
| Spark | `aidp_cluster_shared_compute`, propiedad compartida; conservar vínculo `cluster_key`. |
| Workflow | `wf_ai_dg_sync_master_catalog`, cuatro tareas ordenadas: `sync_inventory` → `document_metadata` → `publish_metadata` → `replicate_model`; última con ALL_DONE. Una ejecución concurrente, cola deshabilitada. |
| Tablas | 18 JSON canónicos en `aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/`; agregados por `schema.py`, sin segundo modelo editable. |
| Almacenamiento | Bucket de artefactos seleccionado y distinto de Landing/Bronze/Silver/Gold. `oci_artifacts` es esquema, no prueba del bucket físico. |
| Credencial | Referencia OCI compartida `AidpRuntime`, operador e identidad verificados; no duplicar ni rotar como parte de la separación. |

Tablas verificadas: `AI_DG_SCOPE`, `AI_DG_ASSET`, `AI_DG_ASSET_VERSION`, `AI_DG_SCOPE_ASSET`, `AI_DG_EVIDENCE`, `AI_DG_RELATION`, `AI_DG_AGENT`, `AI_DG_RUN`, `AI_DG_EVENT`, `AI_DG_WORK`, `AI_DG_DOCUMENT`, `AI_DG_DOC_EVIDENCE`, `AI_DG_PUBLICATION`, `AI_DG_RULE`, `AI_DG_ASSESSMENT`, `AI_DG_CASE`, `AI_DG_CASE_ASSET`, `AI_DG_DECISION`.

`deploy_studio_install.py` conserva intención antes de POST, recursos, operación y recibos; respuestas inciertas bloquean creación duplicada. Su comparación de workflow tolera únicamente los campos nulos nativos documentados, manteniendo rechazo de deriva efectiva. Prepara el horario pausado y el código solo habilita la periodicidad UTC de treinta minutos tras verificar la primera ejecución exacta. Finalizar instalación deja `validation_stage=TEST_PENDING` (`activate`, línea 328). Esto describe lógica implementada: **no hay evidencia recogida aquí de ejecución, horario efectivo, permisos, calidad documental o conversación en un entorno real**.

## Qué se extrae y qué requiere desacoplamiento

| Conjunto | Tratamiento propuesto |
| --- | --- |
| `apps/backend/app/modules/ai_data_governance/` | Candidato completo de dominio, fuentes, recursos y paquete. Revisar `naming.py`: contiene `database_names`, consumido por Autonomous y relacionado con participantes; no atribuir automáticamente ese helper al módulo independiente. |
| `scripts/modules/ai_data_governance/` | Llevar checks de ambos grafos, renderizador del modelo y adaptador de evaluación, actualizando raíces/imports y sin reciclar recibos con hashes anteriores. |
| `apps/backend/tests/modules/ai_data_governance/` | Llevar regresiones de dominio y ensamblado; desacoplar fixtures del portal. Conservar también `tests/support/ai_dg_fixtures.py` y helpers de evaluación referenciados, tras revisar imports. |
| `app/packages/catalog.py`, `catalog.json`, `aidp.py` | Extraer solo validación y carga del paquete Governance con registro explícito; no copiar catálogo de kits ni descubrimiento de módulos. `deploy_studio_install.py:10` importa el loader común. |
| `app/services/oci/aidp.py`, `contracts.py` | Separar capacidades usadas: transporte firmado, workspaces, archivos/readback, catálogo, jobs/runs, compute, agentes/deployments, permisos, credencial y recibos. La fachada mezcla participantes y módulos; copiarla completa conservaría el monolito. |
| `app/main.py`, `runtime.py`, `models.py`, `config.py` | Evidencia del contrato de autorización, configuración, estado y recuperación que los CLI/hooks deben preservar. No extraer el servidor API del portal ni registro de participantes, login local o administración de kits. |
| `apps/frontend/src/App.tsx` y tests asociados | Evidencia de selección, confirmación, progreso y bloqueo por aceptación. No trasladar GovernanceModuleManager ni sus pantallas React. Los requisitos de operación se integran en Deploy Studio bajo coordinación; el frontend viejo se retira del general cuando se cierre el corte. |
| Terraform, CI y release | Reconstruir cierre propio de paquete/CLI/hooks desde dependencias reales, sin copiar estado, post-apply completo ni Terraform de plataforma/visor. Sin imagen de portal. Coordinación es dueña de Deploy Studio y de la retirada en la fuente. |

### Llamadores y dependencias cruzadas que bloquean una extracción mecánica

1. `apps/backend/app/main.py:310,630` aplica autenticación administrativa y verificación del administrador AIDP seleccionado. Sus rutas en líneas 689–752 son evidencia del ciclo vigente, no rutas a reproducir en Governance. Deploy Studio autentica y revalida la selección; los hooks conservan las comprobaciones efectivas y resultados pending/conflict. Un indicador del navegador no acredita membresía.
2. `services/oci/aidp.py:2975–3026` conserva operation_id y restringe la operación admitida a install con recibo de la familia actual. `:2572` bloquea Agent Hub pendiente de aceptación/publicación; `:3099` bloquea borrado. La presencia de rutas redeploy/delete no prueba soporte operativo.
3. `deploy_studio_install.py:57–70` recibe la fachada OCI completa y llama métodos privados. Sus fases requieren capacidades de catálogo, archivos, compute, agentes, jobs y permisos. El límite independiente necesita capacidades concretas, no un wrapper vacío alrededor del cliente entero.
4. `services/oci/aidp.py:23` reutiliza `identity_hash/shared_credential` de God's Eye View; `modules/ai_market_intelligence/client.py:82` hereda de AidpClient. Conforme al plan común, extraer un cierre mínimo con procedencia y propiedad por producto; se admite una pequeña base repetida inicialmente. No introducir imports entre repositorios hermanos, dependencia de releases del general ni un cuarto framework compartido. La propiedad del recurso cloud compartido sigue siendo única aunque se repita código mínimo.
5. `services/oci/autonomous.py:14` importa `database_names` desde `ai_data_governance/naming.py:6`. El coordinador debe reubicar su dueño compartido antes de retirar Governance; no añadir aliases legacy.
6. `terraform/deploy-studio.json:669–689` incluye Governance en el cierre del hook. `terraform/b_variables.tf:95–102` permite solo God's Eye View en `enabled_vm_modules`. Governance no tiene un módulo VM independiente implementado.
7. `apps/frontend/src/App.tsx:794` comparte GovernanceModuleManager con Market; `:3026` exige ACCEPTED para Agent Hub. `:1109` todavía anuncia borrado de cuatro tablas Delta, incompatible con las 18 actuales y con la operación bloqueada. Ese frontend no se extrae; trasladar a Deploy Studio los bloqueos y datos correctos del contrato, sin habilitar borrado por accidente.

Estos bordes fueron revisados en exploración independiente de solo lectura y reconciliados con los descriptores, instalador, guía y ensambladores. El inventario estático no garantiza ausencia de dispatch dinámico: antes del corte, comprobar el cierre de imports dentro de un checkout aislado sin el monolito en PYTHONPATH.

## Propuesta de código importable y assembly determinista

La separación ya existe parcialmente: `governance_graph.py:17,250` contiene estado/nodos; `documentary_graph.py:22,79,175` contiene estado, nodos y builder con hooks; `response_graph.py` mantiene respuesta. Preservar esa lógica y los hooks de autorización/persistencia. No dividir solo por tamaño.

El problema concreto está en `governance_source.py:81–126`: extrae definiciones con AST/inspect, fabrica un preámbulo en texto y coloca `ACTIVITY_PROGRAM`/`CASE_PROGRAM` como literales. `documentary_source.py:22` ensambla símbolos; `pipeline_source.py:19–63`, `runtime_source.py`, `activity_source.py:10` y `case_source.py:9` ensamblan programas similares. `native_governance.py:28–29,148–189` consume esos programas fijos. No es correcto afirmar que toda la implementación actual sea un string ni sustituir esos comandos fijos por SQL generado por el modelo.

Estructura propuesta, aún no creada:

```text
src/ai_data_governance/
  cli.py                     # entrada CLI para hooks, sin servidor HTTP
  installation/              # reconciliación, recibos, progreso y recuperación
  agents/governance/         # state.py, nodes.py, graph.py, tools.py, factory.py
  agents/documentation/      # mismo límite por responsabilidad
  shared/                    # contratos y lógica realmente compartidos
  native/                    # identidad, transporte, persistencia y entradas AIDP
  tasks/                     # comandos activity/case y tareas Spark importables
aidp/
  manifest.json
  master_catalog/oci_medallion/schemas/oci_artifacts/
    schema.json
    tables/<tabla>.json
  workspaces/default/
    files/agents/{governance,documentation}/
    workflows/wf_ai_dg_sync_master_catalog.json
    compute/aidp_cluster_shared_compute.json
    agent_flow/agents/<agente>.json
    agent_flow/compute/aidp_data_governance_agent_compute.json
package/lab.json
scripts/                     # packaging y validación explícitos
tests/                       # dominio, CLI/hooks, assembly y aceptación
terraform/                   # infraestructura propia, sin estado heredado
  deploy-studio.json         # schema 1, project_id único congelado en primera release
  hooks/                     # preflight y post-apply autocontenidos
docs/                        # operación desde Deploy Studio y herramientas AIDP
```

Los nombres de carpeta propuestos no cambian IDs nativos ni rutas Workspace. Elegir una sola ubicación editable para cada archivo: `src/ai_data_governance/` contiene los módulos importables; `aidp/.../files` conserva entradas y prompts editables declarados o salidas generadas identificadas como tales, nunca una segunda copia mantenida del mismo runtime.

1. Convertir preámbulos y bloques de programa mantenidos en módulos Python importables con imports normales. Mantener contratos, validadores y constantes en su responsabilidad; herramientas separan lectura, diagnóstico y efectos autorizados. Prompts tienen una única fuente, leída por ambos entornos.
2. Proporcionar factories explícitas por agente `factory(runtime) -> compiled_graph`, inyectando modelo, servicios, autorización, persistencia y checkpointer. `external_effects_allowed=false` debe impedir efectos. Las entradas nativas setup/invoke no son por sí solas factories compatibles.
3. Packaging declara una lista ordenada y cerrada de módulos/recursos por entrypoint. Configura solo bindings no secretos y produce bytes UTF-8 legibles, fuentes de assembly, component_revision y SHA-256. Sin scan dinámico, bundles codificados ni carga oculta en runtime. No asumir que AIDP admite módulos auxiliares sin una prueba de importación nativa del candidato.
4. Preservar el transporte actual de comandos fijos donde Spark necesita recibir código: generar esos bytes desde `src/ai_data_governance/tasks/` durante packaging, jamás mantener el programa como string editable. Si el runtime necesita transportar el contenido, declararlo como artefacto generado y verificar su hash; no cambiar a un modo de upload/ejecución no comprobado.
5. Dos builds con bindings idénticos deben producir exactamente rutas/bytes/hashes idénticos. Cambiar código, prompts o descriptores debe alterar revisión y hashes pertinentes. No reescribir una release inmutable ni fabricar recibos de aceptación; una nueva ubicación/importación puede invalidar evidencia previa.

## CLI/hooks, Deploy Studio e infraestructura: new y existing

**Paquete Python y hooks:** exponer instalación, observación, reanudación y actualización mediante comandos y hooks invocados por Deploy Studio. La observación no muta; los comandos de efecto registran intención durable y conservan operación/recursos en respuestas inciertas. Definir contratos explícitos de argumentos, resultados, progreso, errores redactados y recibos; no añadir un servidor HTTP ni contratos OpenAPI/TS al producto. Actualización, redeploy y mantenimiento requieren implementación y aceptación donde el código actual los bloquea; no exponer capacidades falsas. Arko guía responsabilidades y contratos Python; no impone FastAPI, React ni una VM y no se inicializa su plantilla sobre este inventario.

**Administración en Deploy Studio:** la selección del administrador, confirmación de recursos/costes, estado, errores y Resume se presentan en el formulario y monitor comunes, bajo coordinación en CloudTechNext. Governance consume ese contrato sin frontend, diálogo ni login propios. Mantener instalación y aceptación como estados distintos y la operación original tras cerrar la vista. Agent Hub permanece bloqueado mientras TEST_PENDING; acceder al agente se realiza por herramientas nativas AIDP cuando esté aceptado y autorizado.

**Deploy Studio:** entregar `terraform/deploy-studio.json` schema 1, preflight, post-apply, outputs y release de paquete Python/artefactos AIDP inmutables, verificables desde checkout limpio; sin imagen de portal. El consumidor real leído en `D:/dev/codex-cloudtechnext/app/backend/app/services/deployment_source.py:107,350,383,409` exige `extra="forbid"`, admite `secret_inputs` y campos condicionales, pero su lista de `options_source` no incluye descubrimiento AIDP. Para new/existing usar opciones estáticas y OCID explícito validado por preflight. El listado genérico de administradores es capacidad nueva de CloudTechNext bajo coordinación; no declarar un `options_source` inventado antes de que el consumidor lo soporte. Inputs/outputs exactos y fixtures se acuerdan con coordinación. `project_id` será único y se congelará con la primera release. Los secretos protegidos viajan solo por el mecanismo autorizado; no por estado, outputs ni artefactos públicos.

**Administrador e identidad firmante:** Deploy Studio lista candidatos del ámbito y dominio seleccionados, envía un ID estable y revalida en servidor usuario activo, dominio y permisos efectivos antes de instalar y al Resume. Cambiar tenancy, dominio o plataforma invalida una selección anterior. En plataforma existente se comprueban roles AIDP efectivos; en plataforma nueva se verifican las asignaciones autorizadas tras bootstrap y antes de publicar agentes/workflows. Conservar el vínculo administrador/recibo al reanudar. Seleccionar ese usuario no suplanta la identidad firmante del operador ni autoriza otro provisioner; los hooks usan las credenciales autorizadas y delegación admitida. Si no se puede actuar/asignar, preflight bloquea antes de mutar. El selector, su API autenticada y sus tests pertenecen a CloudTechNext, no al paquete Governance.

El recurso `oci_ai_data_platform_ai_data_platform.lab` en `terraform/j_oci_ai_data_platform.tf` crea siempre AIDP en la fuente congelada. Por tanto, **new/existing AIDP es capacidad nueva**, no una opción ya implementada que baste con trasladar. Crear producto independiente no autoriza aplicar sobre el stack combinado después de quitar recursos.

| Modo | Alcance propuesto | Evidencia previa obligatoria |
| --- | --- | --- |
| new | Crear AIDP y workspace explícitos cuando se seleccione, más los recursos Governance y componentes realmente requeridos, mediante Terraform/hooks propios sujetos al contrato común. | Identidades, permisos, workspace, buckets distintos cuando aplique, disponibilidad del modelo, compute, fuente inmutable y propietario de cada recurso. La rama new/existing y sus referencias requieren implementación y tests. |
| existing | Instalar Governance sobre plataforma/workspace externos seleccionados y verificados; conservarlos como external fuera del ciclo de destrucción del producto. No equivale a adoptar una instalación Governance ajena. | OCID y claves exactas, región/endpoints/conectividad, `/roles` con identidad efectiva, permisos de scopes/storage/compute y recibo de lo que cree el producto. Una base Autonomous existente no sustituye AIDP. |
| Resume/update de instalación propia | Reutilizar recibo, identidad y operation_id compatibles de esa instalación; no crear otra ni apropiarse de recursos por nombre. Update/redeploy siguen pendientes de implementación donde la fuente los bloquea. | Recurso y propietario exactos, revisión de origen/destino y estado observado; rechazo sin cambios de formatos no admitidos, propietarios ajenos o resultado incierto. |

No se propone `terraform import`, adopción por nombre, renombrado de direcciones de estado ni creación de credencial/operador alternativo. La separación del repositorio no autoriza a tomar propiedad de recursos compartidos. El plan común define el despliegue independiente por CLI/hooks; aún falta implementar y verificar sus bindings exactos para Governance. Governance no crea ni reutiliza una VM administrativa.

## Riesgos y recuperación

- Doble escritor: antes de cambiar código o compute, detener escritores administrados de forma autorizada y comprobar terminalidad. Un solo dueño de jobs, agentes, horarios, recibos y compute por entorno; no dejar monolito y repositorio nuevo reconciliando el mismo recurso.
- Pérdida de propiedad: distinguir recursos del módulo de plataforma, bucket, esquema, Spark y credencial compartidos. Conservar IDs, permisos y datos; un nombre distinto de repositorio no justifica recreación.
- POST incierto: conservar intento y operación, observar y conciliar antes de repetir. No limpiar un recibo para volver a empezar.
- Rollback: retener artefacto/revisión saludable y bindings verificados. Revertir código solo bajo operación soportada y tras revisar escritores/compatibilidad de datos; **redeploy y delete están bloqueados actualmente**, por lo que no se promete rollback cloud automatizado. Si un cambio requiere migración de tablas, diseñar y autorizar su recuperación antes de ejecutarlo; este plan no incluye DDL destructivo.
- Corte de distribución: actualizar consumidores post-apply, catálogo, release y rutas del portal general coordinadamente; no retirar nada de la fuente antes de demostrar cierre independiente y aceptación. No reproducir esas rutas en Governance. La retirada del monolito pertenece a coordinación.
- Seguridad: conservar validación de scopes, autorización, protección de esquema de control, rechazo de SQL arbitrario y persistencia idempotente. Durante implementación aplicar security-best-practices; cambios efectivos de confianza o modelos persistentes requieren sus guías específicas antes de editar.

## Criterios verificables y única ruta de validación propuesta

La fuente de requisitos es este diagnóstico subordinado al plan común, sin otro plan competitivo. Antes de implementar reconciliar ambos documentos. Adaptar una sola ruta preflight/postflight del proyecto destino; no duplicar checks CLI/MCP. Reutilizar pruebas existentes y dependencias fijadas antes de añadir otras.

| Gate | Criterio de aceptación futuro |
| --- | --- |
| Baseline | Confirmar fuente/estado y closure; registrar checks antes de código, Sentrux baseline/rules y dependencias. No reutilizar baseline del monolito como resultado del repo nuevo. |
| Independencia | Tests/imports y build del paquete Python en checkout sin fuente original ni hermanos en PYTHONPATH; contratos de argumentos/resultados CLI/hooks revisados; ninguna dependencia del servidor, login o frontend del portal general. |
| Modelo/paquete | Exactamente 18 tablas, dos agentes y cuatro tareas; comparar IDs, columnas, descripciones, DAG/orden/reintentos/ALL_DONE y propiedad de computes. `check_aidp_modules.py` adaptado verifica manifest, paths, hashes y sintaxis. |
| Assembly | Repetibilidad exacta en dos builds; entradas generadas importan/compilan; mismas funciones con fixtures en forma modular y empaquetada. Cero secretos en bytes producidos. Hashes/versiones actualizados deliberadamente. |
| Dominio | Mantener regresiones de inventario vacío y tabla descrita, conservación/relleno documental, linaje inequívoco, SQL rechazado, scopes/roles, revisión de evidencia, idempotencia, cancelación y recuperación con recibos. |
| Instalación | Simular readback, drift real, POST incierto, reanudación con misma operación, rechazo de identidad ajena y cómputo/workflow no esperado; no confundir 202 o active con aceptación. |
| Deploy Studio/release | Fixtures schema 1 pasan parser y runner reales, rechazan claves extra y verifican paths, secret_inputs, preflight/post-apply, outputs y errores redactados. Terraform con mocks cubre new/existing sin cambios inesperados en recursos external; paquete/release inmutables se construyen sin repos hermanos ni imagen de portal. |
| Administrador | Tests del consumidor coordinado cubren ID manipulado, usuario inactivo, dominio/ámbito equivocado, selección obsoleta y rol revocado antes de Resume; hooks rechazan bindings sin verificación efectiva. Plataforma nueva verifica asignaciones tras bootstrap, sin suplantar firmante ni crear provisioner alternativo. |
| Grafos | Ejecutar checks de ambos builders con modelo/repositorios/hooks inyectados y sin efectos; comparar ruta/nodos y resultado. CLI factory y versiones deben verificarse, no inferirse por setup/invoke. |
| TEST nativo | Solo con autorización futura: observar revisión servida, permisos con identidad exacta y segundo usuario, resultados de las tareas/tablas, respuestas con evidencia y recuperación de fallos. Instalar y ejecutar son gates distintos; un throttle no cuenta como respuesta aceptada. |
| Horario/PROD | Inspeccionar horario efectivo y primera ejecución completa del DAG exacto antes de habilitarlo. Publicación consultiva PROD permanece gate separado y pendiente de implementación/aceptación y autorización. |

Comandos canónicos actuales a adaptar (no ejecutados aquí): `python -m pytest apps/backend/tests/modules/ai_data_governance`, `python scripts/validation/check_aidp_modules.py`, `python scripts/modules/ai_data_governance/check_ai_dg_documentary_graph.py`, `python scripts/modules/ai_data_governance/check_ai_dg_governance_graph.py`. CI usa Python 3.12 y requirements-dev del backend. No instalar dependencias como parte del diagnóstico.

## Validación efectuada y límites

- Preflight/postflight: no ejecutados, cambio exclusivamente documental en destino vacío; fuente intacta.
- Tests: no ejecutados. `python --version` resolvió al alias de Microsoft Store sin intérprete utilizable; no se intentó instalar ni modificar herramientas. Esto no bloquea la inspección documental, pero no permite afirmar regresiones aprobadas.
- Graphify: informe e índice existentes leídos; obsoletos respecto al commit congelado; no actualizados ni inicializados.
- Sentrux: no ejecutado, documentación solamente. No se evaluaron reglas del destino, que aún no es repositorio.
- Codex: GPT-6.1 Sol High -- recomendado para la extracción de contratos y pruebas de recuperación [Referencia](https://developers.openai.com/api/docs/models/gpt-6.1-sol). Recomendación, no cambio de modelo ni ahorro medido.
- Lectura de Git, descriptores, código, callers y tests; comparación de inventario y comprobación final del documento. Sin Docker, capturas, inferencia, actors, cloud, sincronización de datos ni cambios de estado.
- Comprobación documental PowerShell aprobada: manifiesto con 18 tablas, dos agentes, un workflow y cuatro tareas en el orden esperado; existencia de todos los descriptores de tablas/agentes/workflow/compute; fences Markdown equilibrados y sin marcadores de claves privadas ni OCID concretos en el informe. Inventario externo por literales: 23 archivos. Segunda lectura Git confirmó HEAD congelado y estado limpio. Se corrigieron patrones no compatibles con PowerShell durante la inspección; no se consideran pruebas funcionales.
- Tras la corrección de alcance se verificó todo el documento mediante búsqueda de frontend/portal/API/VM/imagen y comprobaciones PowerShell: propuestas previas incompatibles ausentes, contratos CLI/hooks y administrador presentes, fences equilibrados y sin marcadores de claves privadas. Las rutas históricas del inventario se conservan como evidencia, no como estructura propuesta. Solo se editó este documento.
- Delegación: una exploración acotada de callers externos, solo lectura; aportó los acoplamientos OCI, Autonomous, post-apply y la discrepancia de UI. Sin rework ni medición comparativa de ahorro; tokens no disponibles. No se delegó implementación ni se duplicó baseline.

## Alineación con el plan común y discrepancias resueltas

Revisión del 2026-11-05 incorporando la corrección explícita del usuario y el plan común actualizado: Governance es paquete Python/CLI/hooks sin frontend, API HTTP de portal, login local, VM administrativa ni imagen de portal. Se reemplazaron las propuestas incompatibles en inventario, estructura, administración, distribución y criterios de aceptación. Las referencias al frontend y rutas viejas quedan como evidencia de contratos a retirar o trasladar a Deploy Studio. Arko guía el código Python sin imponer FastAPI/React. Existing incluye una instalación nueva sobre AIDP externo verificado, distinta de Resume de una instalación Governance propia. Se acepta duplicación mínima inicial de adaptadores sin paquete central.

No se detecta una contradicción pendiente con el objetivo común corregido. Persisten brechas de implementación: new/existing AIDP, paquete CLI/hooks autónomo, selector genérico de administrador en CloudTechNext, update/redeploy/recuperación de artefactos soportados y aceptación TEST funcional. El workflow actual puede programarse tras su gate nativo aunque TEST_PENDING; se debe observar y reportar su estado real. La transición de instalaciones combinadas, movimiento de estado, publicación/catálogo y operaciones cloud siguen bajo coordinación y fuera de esta fase.

## Inventario exhaustivo candidato de la fuente congelada

La lista siguiente se obtiene de archivos versionados, no de caches, secretos ni estado. Identifica fuentes/tests a revisar y trasladar selectivamente según las responsabilidades anteriores; no autoriza copiar el monolito. Las rutas se conservarán como evidencia de procedencia aunque cambie la estructura final.

### Fuentes y descriptores del módulo (98)

```text
apps/backend/app/modules/ai_data_governance/__init__.py
apps/backend/app/modules/ai_data_governance/activity_commit.py
apps/backend/app/modules/ai_data_governance/activity_program.py
apps/backend/app/modules/ai_data_governance/activity_records.py
apps/backend/app/modules/ai_data_governance/activity_source.py
apps/backend/app/modules/ai_data_governance/activity_transport.py
apps/backend/app/modules/ai_data_governance/aidp/manifest.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/schema.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_AGENT.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_ASSESSMENT.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_ASSET.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_ASSET_VERSION.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_CASE.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_CASE_ASSET.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_DECISION.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_DOCUMENT.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_DOC_EVIDENCE.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_EVENT.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_EVIDENCE.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_PUBLICATION.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_RELATION.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_RULE.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_RUN.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_SCOPE.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_SCOPE_ASSET.json
apps/backend/app/modules/ai_data_governance/aidp/master_catalog/oci_medallion/schemas/oci_artifacts/tables/AI_DG_WORK.json
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/agent_flow/agents/ai_data_governance.json
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/agent_flow/agents/ai_data_governance_sync_master_catalog.json
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/agent_flow/compute/aidp_data_governance_agent_compute.json
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/compute/aidp_cluster_shared_compute.json
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/files/agents/documentation/documentation_agent.py
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/files/agents/documentation/prompts.md
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/files/agents/documentation/requirements.txt
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/files/agents/governance/governance_agent.py
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/files/agents/governance/prompts.md
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/files/agents/governance/requirements.txt
apps/backend/app/modules/ai_data_governance/aidp/workspaces/default/workflows/wf_ai_dg_sync_master_catalog.json
apps/backend/app/modules/ai_data_governance/caller_transport.py
apps/backend/app/modules/ai_data_governance/case_activity.py
apps/backend/app/modules/ai_data_governance/case_changes.py
apps/backend/app/modules/ai_data_governance/case_commit.py
apps/backend/app/modules/ai_data_governance/case_confirmation.py
apps/backend/app/modules/ai_data_governance/case_policy.py
apps/backend/app/modules/ai_data_governance/case_previews.py
apps/backend/app/modules/ai_data_governance/case_program.py
apps/backend/app/modules/ai_data_governance/case_reader.py
apps/backend/app/modules/ai_data_governance/case_readmission.py
apps/backend/app/modules/ai_data_governance/case_source.py
apps/backend/app/modules/ai_data_governance/case_transport.py
apps/backend/app/modules/ai_data_governance/catalog.py
apps/backend/app/modules/ai_data_governance/catalog_discovery.py
apps/backend/app/modules/ai_data_governance/catalog_metadata.py
apps/backend/app/modules/ai_data_governance/central_sql.py
apps/backend/app/modules/ai_data_governance/code_context.py
apps/backend/app/modules/ai_data_governance/code_usage.py
apps/backend/app/modules/ai_data_governance/constants.py
apps/backend/app/modules/ai_data_governance/consultation.py
apps/backend/app/modules/ai_data_governance/contracts.py
apps/backend/app/modules/ai_data_governance/delta.py
apps/backend/app/modules/ai_data_governance/deploy_studio_install.py
apps/backend/app/modules/ai_data_governance/deployment_bundle.py
apps/backend/app/modules/ai_data_governance/documentary_graph.py
apps/backend/app/modules/ai_data_governance/documentary_hooks.py
apps/backend/app/modules/ai_data_governance/documentary_source.py
apps/backend/app/modules/ai_data_governance/documentation.py
apps/backend/app/modules/ai_data_governance/governance_graph.py
apps/backend/app/modules/ai_data_governance/governance_source.py
apps/backend/app/modules/ai_data_governance/inventory.py
apps/backend/app/modules/ai_data_governance/inventory_writer.py
apps/backend/app/modules/ai_data_governance/journal.py
apps/backend/app/modules/ai_data_governance/lineage.py
apps/backend/app/modules/ai_data_governance/materialize.py
apps/backend/app/modules/ai_data_governance/model_output.py
apps/backend/app/modules/ai_data_governance/naming.py
apps/backend/app/modules/ai_data_governance/native_activity.py
apps/backend/app/modules/ai_data_governance/native_cases.py
apps/backend/app/modules/ai_data_governance/native_documentary.py
apps/backend/app/modules/ai_data_governance/native_governance.py
apps/backend/app/modules/ai_data_governance/native_pipeline.py
apps/backend/app/modules/ai_data_governance/native_sync.py
apps/backend/app/modules/ai_data_governance/outcome_receipts.py
apps/backend/app/modules/ai_data_governance/package/lab.json
apps/backend/app/modules/ai_data_governance/pipeline_source.py
apps/backend/app/modules/ai_data_governance/projection_query.py
apps/backend/app/modules/ai_data_governance/prompts.py
apps/backend/app/modules/ai_data_governance/publication.py
apps/backend/app/modules/ai_data_governance/publication_context.py
apps/backend/app/modules/ai_data_governance/replication.py
apps/backend/app/modules/ai_data_governance/repository.py
apps/backend/app/modules/ai_data_governance/response_graph.py
apps/backend/app/modules/ai_data_governance/runtime_source.py
apps/backend/app/modules/ai_data_governance/schema.py
apps/backend/app/modules/ai_data_governance/service_transport.py
apps/backend/app/modules/ai_data_governance/sync_inventory.py
apps/backend/app/modules/ai_data_governance/task_arguments.py
apps/backend/app/modules/ai_data_governance/workflow.py
apps/backend/app/modules/ai_data_governance/workflow_receipts.py
apps/backend/app/modules/ai_data_governance/workflow_staging.py
```

### Tests del módulo (77)

```text
apps/backend/tests/modules/ai_data_governance/__init__.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_activity.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_activity_cleanup_boundary.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_activity_delivery.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_activity_diagnostics.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_activity_program.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_activity_readonly_recovery.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_activity_recovery_entry.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_activity_writer_cancel_entry.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_caller_transport.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_case_activity.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_case_changes.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_case_confirmation.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_case_context.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_case_policy.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_case_previews.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_case_program.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_case_reader.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_case_readmission.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_catalog.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_catalog_discovery.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_catalog_metadata.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_central_sql.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_central_transport.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_code_context.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_code_usage.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_consultation.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_contracts.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_conversation_focus.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_delta.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_deploy_studio_install.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_deployment_bundle.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_documentary_cycle.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_documentary_hooks.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_documentary_source.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_generated_readback.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_generation_reuse.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_governance_source.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_impact_context.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_inventory.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_inventory_writer.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_journal.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_lineage.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_lineage_tasks.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_materialize.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_metadata_worker.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_model_output.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_model_recovery.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_model_throttling.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_native_activity.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_native_cases.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_native_documentary.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_native_stream_entry.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_native_sync.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_outcome_receipts.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_pipeline_diagnostics.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_portal_bridge.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_projection_query.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_publication.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_publication_controller.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_publication_repository.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_replication.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_repository.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_response_graph.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_response_rendering.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_runtime_source.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_schema.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_service_transport.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_source_recovery.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_standard_layout.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_sync_inventory.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_task_arguments.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_test_adapter.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_workflow.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_workflow_names.py
apps/backend/tests/modules/ai_data_governance/test_ai_dg_workflow_recovery.py
apps/backend/tests/modules/ai_data_governance/test_governance_lifecycle.py
```

### Herramientas propias (4)

```text
scripts/modules/ai_data_governance/ai_dg_test_adapter.py
scripts/modules/ai_data_governance/check_ai_dg_documentary_graph.py
scripts/modules/ai_data_governance/check_ai_dg_governance_graph.py
scripts/modules/ai_data_governance/render_ai_dg_model.py
```

### Referencias externas por literal (23)

No todas se extraen: algunas son tests compartidos, otros módulos o consumidores que coordinación debe actualizar. Es un índice literal complementario, no una prueba de cierre semántico.

```text
.github/workflows/ci.yml
.github/workflows/release.yml
apps/backend/app/main.py
apps/backend/app/packages/aidp.py
apps/backend/app/packages/catalog.json
apps/backend/app/packages/catalog.py
apps/backend/app/services/oci/aidp.py
apps/backend/app/services/oci/autonomous.py
apps/backend/tests/api/test_api.py
apps/backend/tests/fixtures/ai_dg_activity_recovery_entry.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_compatibility.py
apps/backend/tests/packages/test_aidp_manifest.py
apps/backend/tests/packages/test_catalog.py
apps/backend/tests/services/oci/test_aidp.py
apps/backend/tests/services/test_releases.py
apps/backend/tests/support/ai_dg_fixtures.py
apps/frontend/src/App.tsx
apps/frontend/tests/application-settings.test.mjs
apps/frontend/tests/registration-poll.test.mjs
apps/frontend/tests/security.test.mjs
terraform/deploy-studio.json
terraform/tests/test_manifest.py
terraform/tests/test_release_gate.py
```
