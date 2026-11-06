# Memoria de agentes

Governance configura el modelo de los agentes y la base que respalda la memoria administrada por AIDP. Terraform crea o reutiliza Autonomous AI Lakehouse 26ai/DW; el hook habilita las funciones AI mediante el control plane y registra su operación durable.

## Runtime

Los dos agentes usan `AsyncProxyCheckpointClient` de `oracle_memory_clients`, con identificadores separados. Sus grafos compilan con ese checkpointer y el contexto de sesión nativo de `flow_setup`.

El proxy se obtiene de `MEMORY_SERVER_URL`, después `MEMORY_URL` y finalmente `http://127.0.0.1:21100`. Los agentes no reciben ADMIN, DSN o wallet, ni abren una conexión `oracledb` o administran tablas privadas de memoria. Las tablas Delta del catálogo tienen otra finalidad. Oracle describe el almacenamiento de sesiones y memoria en [Agent Memory](https://docs.oracle.com/en/cloud/paas/ai-data-platform/aidug/agent-memory.html).

## Base y credencial

El formulario usa el grupo `database`, `database_profile=new_or_existing` y `existing_database_wallet=none`. Los parámetros y sus condiciones están en la [guía de instalación](deploy-studio.md#parámetros-del-formulario).

Una base nueva usa 26ai/DW, cuatro ECPU, 1 TB, licencia incluida, mTLS y autoscaling desactivado, con `prevent_destroy`. Una existente se consulta por OCID exacto y debe estar AVAILABLE/26ai/DW; se conserva como externa. El hook vuelve a verificar identidad y perfil contra el SDK. External describe la propiedad de infraestructura: AIDP sigue escribiendo sesiones y memoria en esa base al utilizarla.

ADMIN se transmite por `DEPLOY_STUDIO_SECRETS.inputs` sólo al control plane; no llega a los agentes, recibos u outputs. No se solicita wallet. El campo es opcional en el formulario, pero `aidp_mode=new` lo exige en preflight y una base propia en modo `new` lo requiere en Terraform. Puede omitirse en la ruta compatible de plataforma y base existentes con memoria propia READY, cuando no hace falta habilitar AI.

Terraform puede conservar la contraseña de la base propia en state. `sensitive` evita mostrarla, no la cifra: el state requiere protección. No se publican state, credenciales ni recibos reales.

## Asociación inicial

El controlador usa `EnableAiFeatureDetails(vector_db_id, vector_db_admin_cred)` del SDK OCI. El entorno de desarrollo fija su versión en `requirements.txt`; los hooks fuente de Deploy Studio usan el SDK preinstalado en el runner, sin instalar ese archivo. La suite de compatibilidad verifica OCI 2.184.1 en Python 3.12, además del entorno completo de desarrollo. La operación soportada es `enable_ai_feature`; no se ejecuta SQL de memoria. Referencias: [gestión de AI](https://docs.oracle.com/en/cloud/paas/ai-data-platform/aidug/ai-feature-enablement.html), [modelo de habilitación](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/ai_data_platform/models/oci.ai_data_platform.models.EnableAiFeatureDetails.html) y [cliente AIDP](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/ai_data_platform/client/oci.ai_data_platform.AiDataPlatformClient.html).

1. Se verifica la plataforma ACTIVE y la base compatible. Una habilitación inicial exige AI DISABLED; READY/ENABLING ajeno sin recibo propio se rechaza antes de crear otra base.
2. Se guarda la identidad plataforma/base/ownership/operador bajo lease y recibo CAS, con ETag y retry token.
3. La intención `submitting` se persiste antes del POST. Se envía con `if_match` y `NoneRetryStrategy`.
4. El ACK debe aportar un work-request OCID. Se observa ese request y se verifican operación ENABLE_AI_FEATURES, plataforma, compartimento, cronología y estado.
5. Sólo request SUCCEEDED más READY permite guardar la asociación técnica y fijar el ETag posterior.

En el plan inicial de plataforma existing DISABLED, operación install y bucket explícitamente nuevo, preflight puede diferir la lectura del recibo. Esto no demuestra ausencia ni autoriza efectos. Post-apply verifica siempre los controles; si al reanudar la memoria ya está READY, vuelve a leerlos aunque el modo original del bucket sea new.

La ausencia de recibos requiere lectura e inspección autorizadas. Un GET404 aislado, un listado paginado o inválido o un objeto existente que no puede leerse bloquean el bootstrap. El grant inicial requiere ausencia de recibos tanto de memoria como de negocio; no se repone un rol revocado durante una fase intermedia.

## Reanudación y errores

Un rechazo definido se reconoce por `ServiceError` y pares status/code conocidos. Resume revalida autorización, DISABLED y ETag antes de otro intento. Errores de transporte, códigos desconocidos y 408/409/429 son inciertos.

Sin ACK/work request verificable se conserva Pending y no se reenvía ni se adopta READY a ciegas. Se necesita conciliación protegida; no hay un atajo automático para demostrar ese envío perdido. Los fallos terminales se conservan y no se reparan deshabilitando AI. [Errores OCI](https://docs.oracle.com/en-us/iaas/Content/API/References/apierrors.htm).

La cronología usa Date del servidor cuando está disponible. En su ausencia compara con el reloj del runner; un desfase puede bloquear la verificación y requiere revisar sincronización, sin ampliar arbitrariamente una ventana de aceptación.

## Evidencia y límites

El GET de plataforma expone `ai_feature_status`, pero no el OCID de la base. La asociación inicial se acredita **indirectamente** por la solicitud propia, su work request y READY, no por una lectura directa del vínculo. Se requiere una ventana exclusiva frente a cambios manuales. [Modelo AiDataPlatform](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/ai_data_platform/models/oci.ai_data_platform.models.AiDataPlatform.html).

Una verificación posterior exige el mismo ETag READY, compartimento e identidad de base. Cualquier revisión nueva requiere conciliación, incluso si podría ser benigna. Una base nueva no sustituye una asociación registrada por otro deployment.

El recibo es de alcance plataforma dentro del bucket seleccionado. El lease coordina sus workers y `if_match` protege el envío frente a otros controladores; no convierte un cambio manual externo en una operación propia.

Update/redeploy/rollback sólo verifican memoria propia READY. No habilitan, cambian, desvinculan o borran bases, permisos o credenciales. No se alteran sesiones, retención o tablas del proveedor. Deshabilitar AI puede eliminar recursos AI y no se usa como recuperación.

`memory_status=READY` es técnico. No demuestra persistencia efectiva de checkpoints, continuidad entre turnos, aislamiento entre usuarios o calidad funcional. Esas capacidades requieren aceptación nativa; no se acreditan con los tests simulados ni con la publicación de una release.
