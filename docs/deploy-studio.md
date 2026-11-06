# Instalación con Deploy Studio

Deploy Studio ejecuta Terraform y los hooks del paquete. Governance usa `project_id=aidp-ai-data-governance`, nombre visible AIDP AI Data Governance y [repositorio público](https://github.com/jgangini/aidp-ai-data-gobernance). El contrato del formulario está en [`terraform/deploy-studio.json`](../terraform/deploy-studio.json), schema 1.

## Preparar el destino

El operador necesita autorización para los recursos seleccionados: AIDP y sus roles, Object Storage, el modelo OCI Generative AI y Autonomous. Seleccionar un administrador no suplanta al operador. En plataforma existente, ambos deben superar las verificaciones de identidad y permisos correspondientes.

Elige una región compatible con AIDP y el modelo. El runner resuelve tenancy, compartment, namespace de Object Storage, credenciales y un sufijo estable del despliegue; preflight descubre `home_region`.

El bucket de artefactos debe ser privado. Los recibos requieren `OBJECT_READ` y `OBJECT_INSPECT`, además de las escrituras condicionales que consume el instalador. Un GET404 aislado no acredita ausencia: un listado autorizado, completo y acotado debe confirmarla. La falta de permisos bloquea la operación, sin otorgarlos automáticamente.

## Recursos nuevos y existentes

`Services mode` permite elegir `Create new AIDP` o `Use existing AIDP`. Los modos de plataforma, bucket y base son independientes.

| Recurso | `new` | `existing` |
| --- | --- | --- |
| AIDP | Crea la plataforma con `New AIDP name` (valor inicial `aidp_governance`) y su workspace `governance-<deployment_suffix>`. | Usa la plataforma seleccionada y el UUID exacto del workspace; conserva ambos como externos. |
| Artefactos | Crea un bucket privado con versionado y `prevent_destroy`. | Usa el bucket indicado sin asumir su propiedad. |
| Memoria | Crea Lakehouse 26ai/DW, cuatro ECPU, 1 TB, licencia incluida, mTLS, autoscaling desactivado y `prevent_destroy`. | Lee el OCID exacto y exige AVAILABLE, versión 26ai y workload DW; Terraform no asume su propiedad ni cambia su configuración. |

En AIDP existente debe estar disponible el Spark compartido esperado, `aidp_cluster_shared_compute`. El instalador no crea otro como reparación. Un AI Compute ajeno, fallido o ambiguo no se adopta ni se borra para obtener un pase.

La memoria admite habilitación propia sobre una plataforma DISABLED. READY/ENABLING sin recibo propio compatible se rechaza. Reutilizar una plataforma ya habilitada requiere la asociación registrada y su revisión intacta; no basta elegir una base y observar READY.

## Parámetros del formulario

| Campo | Uso y condición |
| --- | --- |
| `aidp_mode` | `Services mode`: `Create new AIDP` (`new`) o `Use existing AIDP` (`existing`); valor inicial `new`. |
| `new_aidp_name` | `New AIDP name`: texto junto a `Services mode`, obligatorio y visible en new; valor inicial `aidp_governance`. Se envía a Terraform como nombre visible de la plataforma creada. |
| `existing_ai_data_platform_ocid` | Selector de plataformas AIDP; obligatorio y visible en existing. |
| `existing_workspace_key` | `Existing workspace`: selector `oci_aidp_workspaces` de workspaces reales de `existing_ai_data_platform_ocid`; conserva su UUID canónico. Obligatorio y visible en existing. |
| `identity_domain_id` | Dominio seleccionado desde `oci_identity_domains`; se guarda su OCID. |
| `admin_user_ocid` | `AIDP administrator`: administrador activo del dominio, listado por `oci_aidp_administrators`; se guarda su OCID estable. |
| `artifacts_mode` | `Artifacts bucket mode`: `Create new bucket` (`new`) o `Use existing bucket` (`existing`); valor inicial `existing`. |
| `artifacts_bucket_name` | `New artifacts bucket name`: nombre explícito, obligatorio y visible en new. Preflight también devuelve en este binding el nombre canónico cuando se selecciona un bucket existente. |
| `artifacts_existing_bucket_name` | `Existing artifacts bucket`: selector `oci_active_buckets` por nombre exacto; obligatorio y visible en existing. |
| `model_id` | `Select Model`: modelo de los agentes desde `oci_genai_chat_models`; selección inicial por el nombre `xai.grok-4.7` (Grok 4.7). CTN lo resuelve al ID regional real, que debe seguir disponible en la región seleccionada. |
| `autonomous_database_mode` | `Database mode`: `Create new database` (`new`) o `Use existing database` (`existing`); valor inicial `new`. |
| `autonomous_database_version` | `Database profile`, sólo en new: perfil `26ai:DW`; el runner produce versión `26ai` y workload `DW`. |
| `existing_autonomous_database_ocid` | `Existing Autonomous Database`: selector `oci_autonomous_databases`, visible y obligatorio en existing; conserva el OCID exacto de la Lakehouse compatible. |
| `autonomous_database_admin_password` | `Database admin password`: secreto sin valor predeterminado. Su obligatoriedad efectiva depende de la ruta de plataforma/base y de la asociación registrada. |

La UI agrupa plataforma en `aidp_platform`, dominio/administrador en `identity`, bucket en `artifacts`, modelo en `enterprise_ai` y Autonomous en `database`. El renderer común de CTN controla presentación y orden. El formulario instala con la operación predeterminada `install`; no ofrece un selector de mantenimiento. Los comandos administrativos y de recuperación permanecen disponibles según el [contrato de operación](contracts.md#operaciones).

Las etiquetas, opciones y etapas del formulario están en inglés. La documentación mantiene el español. Seleccionar un bucket o una base existentes no transfiere su propiedad ni acredita los permisos; los hooks conservan sus verificaciones.

El nombre nuevo admite entre 1 y 255 caracteres: empieza por letra ASCII o número y permite letras ASCII, números, espacios, puntos, guiones y guiones bajos. Es un nombre visible, no una selección por identidad: existing continúa usando el OCID elegido. Los nombres internos de políticas, memoria y workspace conservan su sufijo de despliegue.

El modelo configurado usa el ID regional devuelto por el inventario. `xai.grok-4.7` es el nombre usado para resolver la selección inicial por coincidencia única; la versión mostrada en el label no se concatena al ID. Se conservan las validaciones de compartimento y destino. El valor inicial no cambia por sí mismo el modelo de una instalación existente.

### Cuándo proporcionar ADMIN

El campo es opcional en el manifiesto, pero no en todas las ejecuciones:

- `aidp_mode=new` exige la contraseña durante preflight, incluso al reanudar o mantener ese contexto.
- `autonomous_database_mode=new` exige una contraseña válida para declarar y conservar la base propia en Terraform.
- Una habilitación nueva o un reintento admitido necesita ADMIN para el control plane.
- Puede omitirse al verificar plataforma y base existentes con asociación propia READY compatible, sin necesidad de habilitar AI.

La contraseña tiene entre 12 y 30 caracteres. La validación Terraform exige mayúscula, minúscula y número, y rechaza comillas o la palabra admin. Se entrega mediante secretos protegidos; no llega a los agentes. No se requiere wallet ni contraseña de wallet. Consulta [memoria](agent-memory.md) para las condiciones completas.

## Ejecutar una instalación

1. Selecciona una release inmutable y elige los recursos mediante `Services mode`.
2. Completa destino, recursos, identidad, modelo y credencial ADMIN cuando corresponda.
3. Ejecuta preflight y revisa el plan. Una ruta inicial DISABLED con bucket nuevo puede diferir la lectura de recibos hasta que exista el bucket; esto no demuestra ausencia ni autoriza grants o habilitación.
4. Autoriza el apply según el flujo de Deploy Studio. Después de Terraform, el hook verifica almacenamiento, propiedad, identidad y recibos antes de actuar.
5. El hook habilita o verifica la memoria y continúa la instalación de agentes, tablas y workflow. El bootstrap y el workflow documental ejecutan trabajo real y pueden consumir el modelo.
6. Si la fase queda pendiente, reanuda el mismo despliegue. No crees otro para forzar éxito.

## Salidas y plataforma compartida

Usa las salidas finales del post-apply, no únicamente las iniciales de Terraform:

| Salida | Significado |
| --- | --- |
| `ai_data_platform_ocid` | Plataforma exacta creada o seleccionada. |
| `workspace_key` | UUID verificado del workspace; inicialmente vacío en Terraform para plataforma nueva. |
| `autonomous_database_id` | OCID de la base de memoria creada o reutilizada. |
| `memory_status` | READY técnico de la asociación verificada por el controlador. |
| `resource_ownership` | Marca plataforma, workspace, artefactos y base como owned/external. |
| `identity_domain_id`, `admin_user_ocid`, `model_id` | Selecciones vinculadas al despliegue. |

Otros productos pueden recibir el AIDP y workspace verificados en su modo existente. No deben crear otra plataforma ni copiar state para agregarse a ella. Compartir AIDP no transfiere propiedad de recursos Governance.

`TEST_PENDING` y READY técnico no acreditan conversaciones, persistencia de sesiones ni aceptación funcional OCI. La publicación consultiva PROD no está implementada. Para mantenimiento consulta [operación](contracts.md).
