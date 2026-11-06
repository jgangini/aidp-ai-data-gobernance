# Memoria de agentes en Governance

Governance selecciona el modelo de sus agentes y aprovisiona o reutiliza Oracle Autonomous AI Lakehouse para la memoria administrada de AIDP. El instalador vincula la base mediante la API de control plane; los agentes conservan su proxy de memoria nativo. No se copian las tablas SQL de participantes de Starter Kits.

## Runtime y modelo

`model_id` se selecciona en Deploy Studio, dentro de `enterprise_ai`, y llega al bundle y a los clientes LLM de los dos agentes. `native_governance.py` y `native_documentary.py` usan `oracle_memory_clients.client.AsyncProxyCheckpointClient`, con identidades separadas y `flow_setup` para la sesión. Los grafos compilan con ese cliente como checkpointer.

El proxy usa `MEMORY_SERVER_URL`, después `MEMORY_URL` y finalmente `http://127.0.0.1:21100`. El agente no abre una conexión `oracledb`, no recibe ADMIN/DSN/wallet y no administra tablas privadas del proveedor. Las dieciocho tablas Delta del catálogo tienen otra finalidad. Oracle confirma que sesiones y memoria residen en la Lakehouse configurada para AIDP. [AI Memory](https://docs.oracle.com/en/cloud/paas/ai-data-platform/aidug/ai-memory.html).

## Formulario y Terraform

El schema 1 usa `database_profile=new_or_existing` y `existing_database_wallet=none`. Todos los campos siguientes pertenecen al grupo `database` del renderer común CTN:

| Campo | Consumo real |
| --- | --- |
| `autonomous_database_mode` | Crear `new` o reutilizar `existing`. |
| `autonomous_database_version` | Perfil nuevo `26ai:DW`; el transform entrega versión y workload a Terraform. |
| `existing_autonomous_database_ocid` | OCID exacto de una base AVAILABLE/26ai/DW; sólo visible en existing. |
| `autonomous_database_admin_password` | Secreto protegido para crear la base o habilitar AI; no se consume para verificar una asociación propia ya READY. |

La base nueva tiene cuatro ECPU, 1 TB, licencia incluida, autoscaling desactivado, mTLS y `prevent_destroy`. Una existente se consulta sin asumir su propiedad ni cambiarla. La salida `resource_ownership.memory_database` distingue owned/external y el hook vuelve a comprobar el OCID y el perfil con el SDK.

No hay wallet ZIP ni contraseña de wallet. La credencial ADMIN llega únicamente por `DEPLOY_STUDIO_SECRETS.inputs`, se usa en control plane y no se escribe en recibos ni outputs. Terraform conserva secretos sensibles en state para una base propia: `sensitive` evita mostrarlos, no los cifra; el state del runner requiere protección. Para mantener ese recurso propio Terraform necesita su credencial declarada. En existing, el valor puede estar vacío si sólo se verifica una asociación propia READY; preflight exige el secreto cuando la ruta realmente puede habilitar AI.

## SDK y asociación durable

El SDK del runner está fijado en `oci==2.189.0`, con lock actualizado y regresiones. La versión anterior 2.160.3 no incluía el modelo ni la operación necesarios. Esto no cambia los paquetes del runtime nativo de agentes ni acredita su paridad de versiones.

`managed_memory.py` usa `EnableAiFeatureDetails(vector_db_id, vector_db_admin_cred)` y `enable_ai_feature`. No llama a SQL. El contrato está documentado en [AI Feature Management](https://docs.oracle.com/en/cloud/paas/ai-data-platform/aidug/ai-feature-enablement.html), [modelo de habilitación](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/ai_data_platform/models/oci.ai_data_platform.models.EnableAiFeatureDetails.html) y [cliente AIDP](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/ai_data_platform/client/oci.ai_data_platform.AiDataPlatformClient.html).

Antes del envío se verifica DISABLED y se publica un recibo CAS bajo lease, con plataforma/base/ownership/operador, ETag y retry token. Se usa `if_match` y `NoneRetryStrategy`. La intención `submitting` se guarda antes del POST; el ACK debe aportar un work-request OCID. Se observa el mismo request, comprobando operación ENABLE_AI_FEATURES, plataforma, compartimento, cronología y estado. Sólo SUCCEEDED más READY permite completar la fase técnica.

El límite temporal usa Date del servidor cuando existe; en su ausencia exige coherencia con el reloj del runner. Un runner adelantado puede bloquear la conciliación de ese caso fallback y requiere revisar sincronización, sin ampliar arbitrariamente la ventana.

Un rechazo definido se reconoce únicamente por tipo ServiceError y pares status/code conocidos; la reanudación revalida autorización, DISABLED y ETag antes de un nuevo intento. 408/409/429, códigos desconocidos y errores de transporte son inciertos. Sin ACK verificable se conserva Pending y no se reenvía ni se adopta READY a ciegas. Ese caso necesita conciliación protegida; no existe un atajo automático que pruebe el request perdido. [Errores OCI](https://docs.oracle.com/en-us/iaas/Content/API/References/apierrors.htm).

## Evidencia de asociación y límites

El GET de plataforma publicado expone `ai_feature_status`, pero no el OCID de la base. La primera asociación se acredita **indirectamente** por el envío propio ligado a la base exacta, su work request y READY; no es un readback directo del OCID asociado. Se requiere una ventana exclusiva frente a cambios manuales. [Modelo AiDataPlatform](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/ai_data_platform/models/oci.ai_data_platform.models.AiDataPlatform.html).

Después se fija el ETag READY. Una verificación posterior exige el mismo ETag, compartimento e identidad de base; cualquier cambio de revisión requiere conciliación, incluso si podría ser benigno. Así no se acepta silenciosamente una asociación cambiada. No se adopta una plataforma READY/ENABLING ajena sin recibo compatible, y preflight bloquea ese caso antes de crear otra ADB. Una base nueva no sustituye una asociación ya registrada por otro deployment.

El recibo de memoria es de alcance plataforma dentro del bucket seleccionado. Su lease protege los workers que lo usan; `if_match` protege el envío concurrente frente a otros buckets/controladores. La ausencia de ambos recibos, memoria y negocio, es necesaria para el grant inicial del administrador. Reanudar en la fase intermedia no repone un rol revocado.

Update/redeploy/rollback sólo verifican una asociación propia ya READY: no habilitan, cambian, desvinculan ni borran bases, permisos o credenciales. Deshabilitar AI puede eliminar recursos AI y nunca se usa como recuperación. No se cambian retención, sesiones ni tablas del proveedor. El rollback de artefactos conserva la base de memoria.

## Validación y aceptación

Las regresiones locales usan el modelo/errores reales del SDK y transporte simulado, con CAS/lease, ACK incierto, rechazos tipados, reanudación, READY ajeno, ETags, identidades, cronología y secretos. Terraform comprueba new/existing y perfiles inválidos con mocks. El hook escribe el contrato real CTN `DEPLOY_STUDIO_OUTPUT`.

`memory_status=READY` es un resultado técnico de control plane. No demuestra continuidad de sesión, aislamiento entre usuarios, persistencia efectiva de checkpoints ni calidad funcional. Esas verificaciones requieren prueba nativa autorizada. Los despliegues permanecen detenidos por el usuario: no se ejecutó OCI, APPLY, inferencia, Browser ni Docker compartido en esta tarea.
