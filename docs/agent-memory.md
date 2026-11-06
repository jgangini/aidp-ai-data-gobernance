# Memoria de agentes en Governance

Este documento distingue el runtime implementado del aprovisionamiento Autonomous pendiente. La memoria de agentes y la selección de su modelo corresponden a Governance. No se trasladan las tablas SQL de participantes de Starter Kits como sustituto de la memoria nativa.

## Implementado

`model_id` se selecciona en Deploy Studio y llega al bundle y a los clientes LLM de los dos agentes. El campo pertenece al grupo `enterprise_ai`.

`native_governance.py` y `native_documentary.py` instancian `oracle_memory_clients.client.AsyncProxyCheckpointClient`. Usan `MEMORY_SERVER_URL`, después `MEMORY_URL`, y finalmente el proxy local `http://127.0.0.1:21100`. Cada agente tiene un identificador separado; los grafos compilan con ese cliente como checkpointer. No crean una conexión `oracledb`, no reciben un DSN o wallet y no definen tablas SQL de checkpoints.

Oracle documenta que las sesiones y la memoria se almacenan en la Autonomous AI Lakehouse configurada para la instancia AIDP. El proxy es la frontera del runtime; crear una conexión SQL paralela cambiaría ese diseño. Las dieciocho tablas Delta del catálogo tienen otra finalidad. [AI Memory](https://docs.oracle.com/en/cloud/paas/ai-data-platform/aidug/ai-memory.html).

## Pendiente: crear o reutilizar Autonomous y asociarla

El Terraform y los hooks actuales no crean ni vinculan esa base. `database_profile` continúa en `none`; no se añaden selectores, passwords ni wallets que carezcan de consumidor. Esto es una limitación del candidato, no una afirmación de que la memoria nativa funciona sin Autonomous.

El helper del commit fuente congelado intenta usar `EnableAiFeatureDetails` y `enable_ai_feature`, pero el SDK local fijado `oci==2.160.3` no contiene ese modelo ni ese método. Trasladar el helper literalmente fallaría. La documentación actual sí describe el contrato siguiente; antes de implementarlo hay que fijar y validar una versión de SDK que lo soporte, sin actualizar el runtime de agentes por analogía.

| Elemento | Contrato confirmado y límite |
| --- | --- |
| Base de memoria | Autonomous AI Lakehouse 26ai o posterior, nueva o existente, compatible con el destino. |
| Habilitación | `EnableAiFeatureDetails`: `vector_db_id` y ADMIN mediante `vector_db_admin_cred` o `vector_db_admin_secret_id`. |
| Concurrencia | `enable_ai_feature` admite `if_match` y `opc_retry_token`; un envío aceptado no demuestra finalización. |
| Observación | Work request de `ENABLE_AI_FEATURES`; plataforma con `ai_feature_status` DISABLED, ENABLING, READY o FAILED. |
| Asociación exacta | El modelo GET de plataforma publicado no expone `vector_db_id`. READY no demuestra que corresponda al OCID elegido. |
| Credenciales del agente | La API documentada no pide wallet, DSN ni usuario SQL al runtime del agente. No mostrarlos por analogía con el bootstrap de participantes. |

Fuentes oficiales: [AI Feature Management](https://docs.oracle.com/en/cloud/paas/ai-data-platform/aidug/ai-feature-enablement.html), [EnableAiFeatureDetails](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/ai_data_platform/models/oci.ai_data_platform.models.EnableAiFeatureDetails.html), [cliente AIDP](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/ai_data_platform/client/oci.ai_data_platform.AiDataPlatformClient.html), [modelo AiDataPlatform](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/ai_data_platform/models/oci.ai_data_platform.models.AiDataPlatform.html) y [WorkRequest](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/ai_data_platform/models/oci.ai_data_platform.models.WorkRequest.html). Las páginas `latest` no fijan una dependencia reproducible por sí mismas.

## Campos previstos, sólo cuando tengan consumidor

Todos los campos de Autonomous pertenecerán al grupo `database`, dentro del schema 1 y del renderer común CTN:

- Modo nuevo/existente y, para reutilizar, OCID exacto de la base validada.
- Perfil compatible con Lakehouse 26ai y parámetros efectivamente usados por Terraform. No ofrecer versiones/workloads incompatibles.
- Una vía explícita de credencial ADMIN protegida, como secreto efímero o referencia de Vault. No registrar su valor en logs, recibos ni outputs. Crear la base con Terraform puede conservar la contraseña en state aunque el campo sea sensitive; ese almacenamiento debe formar parte del contrato protegido del runner.

No existe aún un formulario de memoria instalable. El campo de modelo actual sí tiene consumidor y permanece disponible.

## Admisión y recuperación que faltan

La implementación debe fijar en recibo CAS la plataforma, la base, su ownership, la intención y el work request antes de considerar la asociación terminada. Una respuesta incierta se observa; no autoriza reenviar o crear otra base a ciegas.

Una plataforma existente en READY sin recibo propio no se adopta sólo por ese estado: falta verificar la asociación exacta. Para DISABLED, habilitar exige autorización y validación de la base; ENABLING se observa. No se conoce aquí una operación segura para cambiar la base preservando memoria y agentes.

Deshabilitar AI elimina recursos AI según Oracle; no se usa como reparación o rollback. La base, sus credenciales y la asociación quedan fuera del rollback de artefactos. Tampoco se modifican retención, memoria compartida, sesiones ni tablas administradas por el proveedor.

Las regresiones necesarias incluyen permisos y propiedad, identidad de base, rechazo de READY ajeno, reanudación tras resultado incierto, protección de secretos y ausencia de cambios de datos/credenciales durante rollback. La continuidad de sesión, aislamiento entre usuarios y persistencia reales requieren una prueba nativa autorizada. Los despliegues permanecen detenidos por instrucción del usuario; este análisis no operó OCI.
