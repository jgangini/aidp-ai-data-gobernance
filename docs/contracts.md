# Operación y recuperación

Governance se opera desde Deploy Studio sobre una instalación y un destino identificados. El [manifiesto](../terraform/deploy-studio.json) define el formulario y los hooks; el [manifiesto AIDP](../src/ai_data_governance/aidp/manifest.json) define agentes, tablas y workflow. Los hashes de los programas distribuidos están en [`package/lab.json`](../src/ai_data_governance/package/lab.json).

## Identidad y autorización

El runner firma con las credenciales del operador. El dominio y el administrador se seleccionan por OCID estable; no cambian el signer. Se verifica usuario activo, dominio y roles efectivos, incluidos grupos y herencia.

El grant inicial sólo se permite para `new` + `install` y ausencia verificada de ambos recibos, negocio y memoria. Una ejecución posterior no repone una revocación. Un workspace con control Governance ajeno sin recibo propio bloquea antes de conceder roles o habilitar memoria.

Los recibos se almacenan bajo `.control/ai_data_governance/installations/<digest>/` en el bucket seleccionado. Un GET404 no prueba ausencia: el listado autorizado exacto debe estar completo y no contener el objeto. Si falta acceso, hay cursor o metadata inválida, la operación se detiene. No se amplía IAM automáticamente.

## Operaciones

| Operación | Comportamiento |
| --- | --- |
| `install` | Habilita/verifica memoria propia, instala los recursos del paquete y ejecuta sus gates nativos. |
| `resume` | Continúa la operación original, sus identidades, candidato, fuente y fase durable. |
| `update` | Publica el candidato compatible en los mismos recursos, con pausa, backup, refresh y verificación. |
| `redeploy` | Usa la misma ruta de mantenimiento de artefactos y refresh sobre la instalación propia. |
| `rollback` | Restaura los artefactos previos respaldados y refresca los agentes existentes. |

Para reintentar conserva `deployment_id`, operación, tag/SHA, contexto y destino. Cambiar de release en una operación pendiente no es Resume. Para actualizar se necesita un contexto de actualización autorizado sobre la misma instalación y state; no aplicar un plan que sustituya plataforma o base para simular mantenimiento.

Una operación de negocio terminada es idempotente y conserva su resultado histórico; no equivale a un healthcheck nuevo. Las verificaciones previas de identidad y memoria siguen aplicándose al ejecutar el hook.

## Estados y códigos

| Resultado | Código CLI | Acción |
| --- | ---: | --- |
| Finalización técnica | 0 | Revisar estado y continuar la aceptación funcional correspondiente. |
| Pendiente | 3 | Observar o reanudar el mismo despliegue y candidato. |
| Fallo | 1 | Revisar la evidencia protegida y la causa antes de reintentar. |
| `update_failed_restored` | 1 | La revisión anterior se restauró, pero el update sigue fallido. |
| `restore_failed` | 1 | Conservar el fallo original y el error de recuperación; Resume continúa la restauración. |
| `rollback_complete` | 0 | Artefactos previos restaurados y verificados técnicamente. |

La instalación finaliza en `TEST_PENDING`. READY/ACTIVE y los códigos de éxito no acreditan conversaciones, calidad de respuestas o persistencia real de checkpoints. No están implementados borrado, transferencia de estado ni publicación consultiva PROD.

## Exclusión de workers y reintentos

Los recibos usan escrituras condicionales, un lease renovable y fencing. Un worker cuyo lease venció no puede escribir recibos ni iniciar nuevas mutaciones. Esto no cancela una solicitud ya enviada al servicio.

Las intenciones se guardan antes de los POST. Un resultado incierto se observa; no se repite a ciegas. Los refreshes de candidato y restauración tienen journals separados. Un rechazo definitivo registrado puede admitir Resume explícito; 408/409/429 y errores desconocidos no se consideran prueba de ausencia de efectos.

Para memoria, un envío sin ACK/work request verificable permanece pendiente y necesita conciliación protegida. No se interpreta READY ajeno como confirmación del envío perdido. Las reglas específicas están en [memoria de agentes](agent-memory.md).

## Actualización de artefactos

Antes de pausar o sobrescribir, se respaldan y releen por SHA-256 los catorce archivos del bundle, los dos descriptores de agente, workflow/schedule y las definiciones, despliegues e identidad previa. Los objetos de backup son inmutables y el recibo publica sus referencias por CAS después de comprobarlos.

Cada objeto admite hasta 4 MiB. Se conservan generaciones sin borrado automático; cien generaciones de snapshots requieren revisión de retención antes de otro update. Los backups no sustituyen copias de datasets o infraestructura.

El mantenimiento exige identidades y recursos propios, bytes originales verificables y compatibilidad de rutas, modelo y almacenamiento. Rechaza archivos añadidos/eliminados, mezcla de revisiones inesperada, copias corruptas y cambios ajenos. La memoria debe tener asociación propia READY compatible; update/redeploy/rollback no la habilitan ni la reparan.

Después de pausar, se drenan writers con una observación completa de claves y estados, que se verifica otra vez antes de escribir. Se suben y releen los bytes exactos y se refrescan los mismos agentes y AI Compute. Estado ACTIVE y fecha de actualización forman el gate técnico de refresh; no prueban una conversación ni todos los bytes servidos por el runtime.

Las operaciones de mantenimiento no crean recursos, cambian permisos/credenciales, ejecutan DDL, inician tasks ni invocan modelos. Reactivar un schedule UNPAUSED sí puede permitir ejecuciones futuras.

## Restauración y frontera de datos

Ante update o refresh fallido se conserva la causa original y se restauran sólo los artefactos/definición propios. Se refresca la revisión anterior y se repone el schedule exacto: un horario PAUSED permanece PAUSED. La revisión saludable efectiva se conserva separada del candidato fallido.

La intención de reactivar el schedule es durable. Si se pierde la respuesta de una activación propia ya aplicada, Resume puede conciliarla verificando archivos, refreshes y workflow objetivo. Una ejecución legítima posterior a ese corte no se trata como actividad anterior que deba revertirse.

Antes de un rollback o restore, cualquier run nuevo respecto al watermark —incluso terminado— o una historia incompleta exige conciliación de datos antes de cambiar archivos o schedule. El instalador no borra ni revierte filas, tablas, resultados de modelos o la base de memoria.

La API de archivos de workspace no aporta un CAS observado. El lease coordina workers del instalador, pero no editores externos: se necesita una ventana exclusiva y cualquier deriva observada bloquea la operación.

## Protección del entorno

Limita el acceso de escritura al bucket de controles a las identidades autorizadas. Quien puede alterar recibos y políticas del bucket está dentro de la frontera de confianza.

El CLI recibe `DEPLOY_STUDIO_CONTEXT`, credenciales protegidas en `DEPLOY_STUDIO_OCI_CONFIG` y `DEPLOY_STUDIO_OCI_KEY`, y secretos en `DEPLOY_STUDIO_SECRETS`. Exige ambos archivos de credenciales; no recurre a una configuración local por defecto. Los mensajes upstream se redactan. No se publican `.oci`, claves, state, secretos, recibos reales ni logs privados en Git o releases.

El contrato del runner depende de la fase:

| Fase | Contexto de compartimento | Archivo de resultado JSON |
| --- | --- | --- |
| Preflight | `compartment` es un string: nombre solicitado con `compartment_mode=new`, OCID con `existing`. Un nombre nuevo aún no identifica un recurso OCI. | `DEPLOY_STUDIO_RESULT` |
| Post-apply | `compartment` es un objeto con `id` resuelto; los bindings aplicados llegan en `terraform_outputs`. | `DEPLOY_STUDIO_OUTPUT` |

No se usa la variable de la otra fase como alternativa. También los errores de contexto o credenciales se escriben como JSON en el archivo correspondiente. El manifiesto declara todas las claves que el hook puede devolver en `outputs`; Deploy Studio rechaza salidas no declaradas.

Las herramientas conservan la protección del esquema framework, el rechazo de SQL arbitrario y la admisión explícita de efectos. El proceso de evaluación no aísla a un worker autorizado malicioso; la protección del runner y sus permisos sigue siendo necesaria.
