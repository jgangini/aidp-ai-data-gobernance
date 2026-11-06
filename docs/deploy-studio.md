# Instalación con Deploy Studio

Deploy Studio ejecuta Terraform y los hooks del paquete. Governance usa `project_id=aidp-ai-data-governance`, nombre visible AIDP AI Data Governance y [repositorio público](https://github.com/jgangini/aidp-ai-data-gobernance). El contrato del formulario está en [`terraform/deploy-studio.json`](../terraform/deploy-studio.json), schema 1.

## Preparar el destino

El operador necesita autorización para los recursos seleccionados: AIDP y sus roles, Object Storage, el modelo OCI Generative AI y Autonomous. Seleccionar un administrador no suplanta al operador. En plataforma existente, ambos deben superar las verificaciones de identidad y permisos correspondientes.

Elige una región compatible con AIDP y el modelo. El runner resuelve tenancy, compartment, namespace de Object Storage, credenciales y un sufijo estable del despliegue; preflight descubre `home_region`.

El bucket de artefactos debe ser privado. Los recibos requieren `OBJECT_READ` y `OBJECT_INSPECT`, además de las escrituras condicionales que consume el instalador. Un GET404 aislado no acredita ausencia: un listado autorizado, completo y acotado debe confirmarla. La falta de permisos bloquea la operación, sin otorgarlos automáticamente.

## Recursos nuevos y existentes

Los modos de plataforma, bucket y base son independientes.

| Recurso | `new` | `existing` |
| --- | --- | --- |
| AIDP | Crea `aidp-governance-<deployment_suffix>` y su workspace `governance-<deployment_suffix>`. | Usa la plataforma seleccionada y el UUID exacto del workspace; conserva ambos como externos. |
| Artefactos | Crea un bucket privado con versionado y `prevent_destroy`. | Usa el bucket indicado sin asumir su propiedad. |
| Memoria | Crea Lakehouse 26ai/DW, cuatro ECPU, 1 TB, licencia incluida, mTLS, autoscaling desactivado y `prevent_destroy`. | Lee el OCID exacto y exige AVAILABLE, versión 26ai y workload DW; Terraform no asume su propiedad ni cambia su configuración. |

En AIDP existente debe estar disponible el Spark compartido esperado, `aidp_cluster_shared_compute`. El instalador no crea otro como reparación. Un AI Compute ajeno, fallido o ambiguo no se adopta ni se borra para obtener un pase.

La memoria admite habilitación propia sobre una plataforma DISABLED. READY/ENABLING sin recibo propio compatible se rechaza. Reutilizar una plataforma ya habilitada requiere la asociación registrada y su revisión intacta; no basta elegir una base y observar READY.

## Parámetros del formulario

| Campo | Uso y condición |
| --- | --- |
| `governance_operation` | `install`, `resume`, `update`, `redeploy` o `rollback`; valor inicial `install`. |
| `aidp_mode` | Plataforma `new` o `existing`; valor inicial del formulario `existing`. |
| `existing_ai_data_platform_ocid` | Selector de plataformas AIDP; obligatorio y visible en existing. |
| `existing_workspace_key` | UUID canónico del workspace de esa plataforma; obligatorio en existing. |
| `identity_domain_id` | Dominio seleccionado desde `oci_identity_domains`; se guarda su OCID. |
| `admin_user_ocid` | Administrador activo del dominio, listado por `oci_aidp_administrators`; se guarda su OCID estable. |
| `artifacts_mode` | Bucket `new` o `existing`; valor inicial `existing`. |
| `artifacts_bucket_name` | Nombre explícito del bucket de artefactos. |
| `model_id` | Modelo de los agentes desde `oci_genai_chat_models`. |
| `autonomous_database_mode` | Base de memoria `new` o `existing`; valor inicial `new`. |
| `autonomous_database_version` | Sólo en new: perfil `26ai:DW`; el runner produce versión `26ai` y workload `DW`. |
| `existing_autonomous_database_ocid` | Sólo en existing: OCID exacto de la Lakehouse compatible. |
| `autonomous_database_admin_password` | Campo secreto sin valor predeterminado. Su obligatoriedad efectiva depende de la ruta de plataforma/base y de la asociación registrada. |

La UI agrupa plataforma/operación en `aidp_platform`, dominio/administrador en `identity`, bucket en `artifacts`, modelo en `enterprise_ai` y Autonomous en `database`. El renderer común de CTN controla presentación y orden.

### Cuándo proporcionar ADMIN

El campo es opcional en el manifiesto, pero no en todas las ejecuciones:

- `aidp_mode=new` exige la contraseña durante preflight, incluso al reanudar o mantener ese contexto.
- `autonomous_database_mode=new` exige una contraseña válida para declarar y conservar la base propia en Terraform.
- Una habilitación nueva o un reintento admitido necesita ADMIN para el control plane.
- Puede omitirse al verificar plataforma y base existentes con asociación propia READY compatible, sin necesidad de habilitar AI.

La contraseña tiene entre 12 y 30 caracteres. La validación Terraform exige mayúscula, minúscula y número, y rechaza comillas o la palabra admin. Se entrega mediante secretos protegidos; no llega a los agentes. No se requiere wallet ni contraseña de wallet. Consulta [memoria](agent-memory.md) para las condiciones completas.

## Ejecutar una instalación

1. Selecciona una release inmutable y `install`.
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
