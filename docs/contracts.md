# Contratos y operación

## Recursos y código

El contrato único es `src/ai_data_governance/aidp/manifest.json`; las fuentes y hashes de paquete están en `package/lab.json` dentro del mismo módulo. Se conservan los dos agentes, 18 tablas `oci_medallion.oci_artifacts` y `wf_ai_dg_sync_master_catalog` de cuatro tareas. El esquema no identifica el bucket físico. `default` vincula el workspace seleccionado; no crea otro workspace por copiar carpetas.

Los grafos importables separan composición, estado y nodos en `governance_{graph,state,nodes}.py` y `documentary_{graph,state,nodes}.py`. Herramientas y efectos permanecen en consulta, transportes, repositorio, publicación y casos; los prompts tienen una fuente por agente en `aidp/workspaces/default/files/agents/`. `factories.py` exige hooks, checkpointer y efectos externos deshabilitados para evaluación portable. Los adaptadores nativos no son factories simuladas.

El assembly es explícito y determinista. Los programas de actividad y casos siguen siendo comandos fijos generados desde módulos Python importables; no son código escrito por el modelo. `assembly_prelude.py` mantiene el preámbulo como Python editable. El manifiesto declara fuentes y bytes configurados reciben hashes antes de publicarse. No hay descargas ni imports del monolito en ejecución.

## Deploy Studio

`terraform/deploy-studio.json` schema 1 declara preflight y post-apply. Usa `admin_user_ocid` e `identity_domain_id`. El selector genérico `oci_aidp_administrators` se integra en CloudTechNext bajo coordinación. El manifiesto se validó con la clase Pydantic real del consumidor; la extracción del archivo distribuido y los entrypoints se comprueban aparte. Eso no acredita ejecución de los hooks en el runner ni una instalación nativa.

Preflight lee el contexto en `DEPLOY_STUDIO_CONTEXT`, usa la configuración autorizada en `DEPLOY_STUDIO_OCI_CONFIG` y escribe `DEPLOY_STUDIO_RESULT`. Comprueba el paquete y el usuario activo del dominio; para existing exige rol efectivo AIDP, incluyendo grupos y roles heredados. El operador firma; seleccionar administrador no permite suplantarlo ni crear otro provisioner. En new, el administrador se asigna por el operador autorizado al rol nativo existente después del bootstrap y se verifica antes de publicar agentes/workflows. No se crea otro rol administrativo.

Terraform crea AIDP/workspace y bucket únicamente según `new`; `existing` requiere OCID/key explícitos y conserva plataforma/workspace/bucket como externos. La salida de ownership y el administrador deben coincidir con la selección antes de aplicar hooks. El Spark compartido existente se verifica y registra como externo; en plataforma nueva se crea con el descriptor explícito. Un compute AI ajeno, fallido o invisible en historial no se adopta ni elimina automáticamente.

## Instalación, Resume, update y redeploy

```powershell
.venv/Scripts/python.exe -m ai_data_governance.cli install --context <contexto-autorizado.json>
.venv/Scripts/python.exe -m ai_data_governance.cli resume --context <mismo-contexto.json>
.venv/Scripts/python.exe -m ai_data_governance.cli update --context <nuevo-contexto-autorizado.json>
.venv/Scripts/python.exe -m ai_data_governance.cli redeploy --context <nuevo-contexto-autorizado.json>
```

`preflight` y `apply` son entrypoints del runner. El campo de formulario schema 1 `governance_operation` selecciona install/resume/update/redeploy y llega en `context.inputs`; install es el valor predeterminado. No se agregan propiedades nuevas al contrato del manifiesto. Resume conserva deployment_id y candidato: se reintenta el despliegue original, no se crea otro deployment seleccionando Resume. La ejecución integral de estas acciones en el runner debe validarse con coordinación antes de catalogar. Los códigos de salida son 0 completado técnicamente, 3 pendiente, 1 fallo; pendiente nunca produce outputs de éxito.

Los recibos propios están en Object Storage bajo `.control/ai_data_governance/installations/<digest>/`. Escrituras condicionales y un lock renovable excluyen doble envío; expiración y fencing impiden que un worker vencido escriba recibos o emita nuevas mutaciones. Un request ya enviado al servicio no se cancela por expirar un lock: las intenciones persistidas bloquean reenvío incierto y exigen conciliación. El recibo vincula plataforma, workspace, dominio, administrador, identidad firmante y revisión. No se adopta una instalación combinada con recibo Workspace sin recibo propio compatible.

Update/redeploy conservan claves y snapshot del manifiesto anterior. Pausan el horario, verifican que los writers sean terminales antes de escribir fuentes, suben el bundle, redespliegan worker documental y consultivo TEST y exigen nuevas ejecuciones de bootstrap/workflow. La misma operación terminada es idempotente. Readback compara contenido y claves; fechas de deployment son un gate técnico parcial, no prueba independiente de todos los bytes servidos por el modelo. Sin fechas/identidades comprobables se conserva Pending.

La instalación termina en `TEST_PENDING`. El horario solo se habilita tras la ejecución técnica completa del DAG. No se ha observado horario ni ejecución nativa en esta migración. No hay borrado, publicación consultiva PROD, transferencia de estado ni rollback cloud automático. El snapshot permite diagnosticar/planificar recuperación; restaurar código anterior requiere su artefacto inmutable y una operación autorizada y verificada, no fabricar hashes ni borrar tablas. Los cambios de recursos compartidos se coordinan antes de operar.

## Identidad y seguridad

El runner, el contexto y su acceso al bucket de recibos son frontera de confianza. Un ID manipulado o usuario revocado debe fallar por comprobación de dominio/activo/roles antes de cada ejecución. Tests cubren usuario inactivo, permisos insuficientes, asignación new sin suplantación y conflicto de recibos. El acceso de escritura al bucket puede alterar controles: limitarlo al operador/runtime autorizado y proteger sus políticas. Un worker autorizado malicioso no se considera aislado por el proceso de evaluación.

`.oci`, llaves, state, outputs privados, logs de proveedor y recibos reales quedan fuera de Git y de releases. Las respuestas del CLI redactan mensajes upstream. Solo se generan bindings no secretos. El runtime conserva protección del esquema framework, rechazo de SQL arbitrario, admisión explícita de efectos, CAS e idempotencia del dominio.
