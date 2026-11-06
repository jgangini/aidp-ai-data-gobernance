# AIDP AI Data Governance

Agentes de documentación y gobierno de datos para Oracle AI Data Platform, instalados desde Deploy Studio. El producto permite seleccionar el modelo OCI Generative AI, el dominio y el administrador, y crear o reutilizar la plataforma y la base de memoria.

Repositorio público: [jgangini/aidp-ai-data-gobernance](https://github.com/jgangini/aidp-ai-data-gobernance). El identificador usado por Deploy Studio es `aidp-ai-data-governance`; el paquete Python es `ai_data_governance`.

## Componentes

| Componente | Función |
| --- | --- |
| Agente documental | Genera y revisa documentación de metadatos dentro del workflow. |
| Agente de gobierno | Consulta el catálogo y gestiona casos de gobierno mediante herramientas con controles de acceso y de efectos. |
| Dieciocho tablas Delta | Conservan inventario, evidencias, documentación, ejecuciones y casos en `oci_medallion.oci_artifacts`. |
| Workflow de cuatro tareas | Sincroniza inventario, documenta y publica metadatos, y replica el modelo del catálogo. |
| Memoria administrada AIDP | Usa Autonomous AI Lakehouse 26ai para las sesiones y checkpoints del proxy nativo de agentes. |
| Recibos y copias de artefactos | Conservan identidad y progreso de las operaciones; permiten reanudar y restaurar archivos propios. |

Governance utiliza Workbench, Spark compartido y AI Compute. No incluye portal web, login local ni VM administrativa.

## Requisitos

- Acceso a Deploy Studio y credenciales OCI protegidas de un operador autorizado en el destino.
- Una región compatible con AIDP y el modelo OCI Generative AI elegido.
- Un Identity Domain y un administrador activo elegible. Seleccionarlos no cambia la identidad que firma las solicitudes.
- Un bucket privado para artefactos y recibos, nuevo o existente. El operador necesita lectura e inspección de objetos para verificar su estado.
- Autonomous AI Lakehouse 26ai/DW, nueva o existente. La base nueva usa cuatro ECPU, 1 TB, licencia incluida y autoscaling desactivado. No requiere wallet.

Una plataforma existente necesita su OCID, el UUID exacto del workspace y el Spark compartido disponible. Para habilitar memoria debe estar DISABLED; una plataforma READY sólo se acepta con recibo propio compatible y sin cambios en la revisión registrada. No se adopta una asociación de memoria ajena.

## Instalación desde Deploy Studio

1. Selecciona una [release inmutable](https://github.com/jgangini/aidp-ai-data-gobernance/releases) y la operación `install`.
2. Elige plataforma nueva o existente y configura los recursos de artefactos y memoria.
3. Selecciona el dominio, el administrador y el modelo de los agentes.
4. Proporciona la contraseña ADMIN mediante el campo protegido cuando sea necesaria. El modo `new` de plataforma la exige en preflight; una base propia en modo `new` también la necesita para su declaración Terraform. Puede omitirse para verificar plataforma y base existentes con memoria propia READY compatible.
5. Revisa el plan y ejecuta el despliegue autorizado. La instalación ejecuta el bootstrap y el workflow documental; puede consumir el modelo seleccionado.

La [guía de Deploy Studio](docs/deploy-studio.md) detalla los catorce parámetros, los modos nuevos/existentes y las salidas. Para compartir el AIDP con otros productos usa `ai_data_platform_ocid` y el `workspace_key` verificado del **post-apply final**; el output inicial de Terraform para un workspace nuevo está vacío.

## Operación

`resume` continúa el mismo despliegue, fuente e identidad. `update` y `redeploy` mantienen los recursos propios y realizan mantenimiento de artefactos. `rollback` restaura los archivos previos y refresca los agentes existentes; no revierte datasets, infraestructura ni la base de memoria.

Un resultado pendiente no debe resolverse creando otro deployment. Un update fallido que restaura la revisión anterior sigue siendo un fallo. Consulta [operación y recuperación](docs/contracts.md) para interpretar los estados y las condiciones que bloquean un cambio.

## Límites vigentes

La instalación termina en `TEST_PENDING`. Los estados READY/ACTIVE y las pruebas locales no acreditan persistencia real de sesiones, aislamiento entre usuarios ni calidad de respuestas. La publicación consultiva PROD, el borrado y la transferencia de estado no están implementados.

La asociación inicial de memoria se acredita mediante la solicitud propia, su work request y READY; el GET de plataforma no devuelve el OCID de la base. Un envío sin confirmación verificable queda pendiente y no se repite automáticamente. Estos límites y la protección de credenciales están en [memoria de agentes](docs/agent-memory.md).

## Documentación

- [Instalación y parámetros de Deploy Studio](docs/deploy-studio.md)
- [Operación, reintentos y recuperación](docs/contracts.md)
- [Memoria e identidad de la base](docs/agent-memory.md)
- [Desarrollo y validación](docs/development.md)
- [Distribución y verificación de releases](docs/release.md)

Licencia [MIT](LICENSE).
