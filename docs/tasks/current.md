# Separación Governance

Implementación autorizada 2026-11-05. Fuente congelada `3c82617fd298933995e954955841007253cc0985`. Remoto privado verificado: `https://github.com/jgangini/aidp-ai_data_governance`, rama main. Commit de código candidato probado y subido: `868387fb9bebcc2a673af06f79a5e2d8c6710b4b`. [CI GitHub 42141257951](https://github.com/jgangini/aidp-ai_data_governance/actions/runs/42141257951) aprobado: Python y Terraform. No hay release publicada. El commit posterior de este estado es exclusivamente documental y no cambia el código probado.

## Implementado

- Extracción explícita desde Git, con archivos/hashes de origen en `provenance.json`, sin `.oci`, estado, caches ni copia del monolito.
- Dominio independiente, dos agentes, 18 tablas y workflow de cuatro tareas; state/nodes/graph separados, herramientas existentes y factories inyectadas. Assembly determinista y preámbulo mantenido en Python importable.
- Cliente OCI reducido a Governance; CLI/hooks sin API, frontend, login, imagen ni VM de portal. Instalar/reanudar/actualizar/redesplegar mediante `governance_operation` en el formulario schema 1 y comandos CLI equivalentes.
- Administrador/dominio estables, usuario activo, roles efectivos y operador firmante separados; asignación administrativa new verificada tras bootstrap. Existing no recibe privilegios por seleccionar un usuario.
- Recibos Object Storage con CAS y lease/fencing. Reanudar conserva operación/candidato/fuente inmutable; update pausa horario, espera writers, conserva IDs/snapshot y exige nuevos runs. Sin adopción de compute oculto ni borrado automático de compute fallido.
- Terraform propio AIDP/workspace y bucket new/existing, ownership explícito, hooks y requirements incluidos en el archivo distribuido. Los externos no pasan a propiedad destructiva del producto.
- CI privado configurado para Python y Terraform con mocks. No contiene credenciales ni ejecuta inferencia.

## Evidencia disponible

- Preflight inicial: baseline Sentrux capturado antes del código. Se conserva en `.sentrux/initial-baseline.json` y se restaura al clonar; no fue recalibrado.
- Postflight final `.local/postflight-release-candidate.txt`: **1.740 tests aprobados en 118.66 s** y compilación Python aprobada. El comando completo termina con error por el gate Sentrux descrito abajo; no se declara postflight aprobado.
- CI del mismo commit: **1.740 tests aprobados en 149.14 s**, compilación y cinco tests Terraform aprobados. La evidencia documental posterior se sube con `[skip ci]` porque no modifica el código ni el manifiesto probado; no se atribuye a ella una nueva ejecución.
- Regresión de precisión ISO/milisegundos: 45 tests del instalador y timestamp aprobados, incluyendo rechazo de runs realmente anteriores. No se relajaron assertions para obtener el pase.
- Terraform fmt/validate y cinco tests con proveedores simulados: aprobados tras el campo de operación final. Sin APIs OCI.
- Clase Pydantic real `DeploymentManifest` de CloudTechNext y `_extract_selected`: archivo staged final aprobado con los nueve campos, entrypoints, include_paths, restricciones de archivos y escáner del consumidor. `governance_operation` es un campo estático del formulario admitido; no una propiedad inventada del contrato.
- Wheel final construida en `.local/dist-reviewed-candidate/`; import desde directorio aislado y assembly repetido de 14 archivos aprobados. SHA-256: `3c19187cf438be9ad64423993201dd5759eb107791c489ab197a01b06535f40d`.
- Escaneo de 239 archivos staged y frontera de imports aprobado; git diff --cached --check sin errores después de normalización LF. `.gitattributes` fija LF para que Git/Windows no invaliden los hashes al clonar en Linux.
- Graphify no configurado, no inicializado. Arko solo guía Python; su perfil CLI fastapi-react no se impuso ni se declara aprobado.

## Gate arquitectónico y pendientes reales

Sentrux se ejecuta sobre una selección explícita de código versionado/no ignorado, excluyendo build, claves, caches y archivos privados. La referencia del destino vacío tenía cero funciones complejas y acoplamiento cero; añadir el producto hace fallar el gate. Última medición acotada final: calidad 0.7697 → 0.6968, acoplamiento 0 → 0.08, ciclos 0 y god files 0, funciones complejas 0 → 6. No hay reglas custom. La validación requerida **no está completa** mientras ese gate permanezca fallido; el candidato no se presenta como arquitectura aceptada ni release final. La coordinación debe revisar este cambio de alcance con evidencia antes de aprobar una referencia de producto.

### Atribución solicitada por coordinación

Se reconstruyó en una carpeta temporal únicamente el dominio/tests y las capacidades mínimas del commit congelado, con las mismas rutas/imports de extracción y el loader explícito necesario. Es una comparación estática acotada, no un candidato ejecutable ni otra referencia aprobada. Se ejecutó el mismo `sentrux gate` contra una copia de la referencia vacía, **sin `--save`**, sin alterar la referencia del destino ni la fuente. Evidencia local: `.local/frozen-capability-comparison.txt`.

| Ámbito | Calidad mostrada | Acoplamiento redondeado | Funciones complejas | Ciclos / god files |
| --- | --- | --- | --- | --- |
| Referencia vacía original | 0.7697 | 0.00 | 0 | 0 / 0 |
| Extracción de capacidades congeladas | 0.6998 | 0.07 | 3 | 0 / 0 |
| Candidato de código 868387f | 0.6968 | 0.08 | 6 | 0 / 0 |

El salto de vacío a extracción explica gran parte del cambio de calidad/acoplamiento, pero **no toda la deuda**: el código nuevo añade tres funciones complejas. Frente a la extracción acotada, calidad cae aproximadamente 0.0030 y acoplamiento mostrado aumenta 0.01. El gate tampoco se declara aceptable por esa comparación: sigue existiendo el aumento de complejidad.

La atribución se confirmó sobre copias temporales del snapshot del candidato: excluir `lifecycle.py` reduce el total 6 → 4, excluir `cli.py` lo reduce 6 → 5; sustituir individualmente cada función siguiente por un cuerpo vacío en esa copia reduce 6 → 5. Ningún cambio de esa prueba se aplicó al repositorio.

- `src/ai_data_governance/lifecycle.py:22`, `RevisionInstaller.agents`: intención, readiness y readback del redespliegue documental/TEST y sus identidades.
- `src/ai_data_governance/lifecycle.py:73`, `run_operation`: admisión de operación, candidato/fuente inmutables, snapshot, pausa y barrera de writers, recuperación e instalación.
- `src/ai_data_governance/cli.py:12`, `settings_for`: validación conjunta new/existing, administrador, ownership y bindings públicos devueltos por Terraform.

No hay `.sentrux/rules.toml` ni excepciones inventadas. La referencia inicial continúa idéntica; estas mediciones diagnostican el fallo, no lo ocultan ni recalibran.

### Alcance probado de actualización y recuperación

`tests/test_lifecycle.py` prueba install/resume y, por separado, **update y redeploy**: conserva claves de ambos agentes, AI Compute, Spark y workflow; pausa horario antes de tocar archivos si hay un writer activo; ejecuta nuevos runs; conserva snapshot anterior; no repite despliegue tras perder la respuesta de una operación ya completada. La suite de dominio conserva checks de bootstrap aditivo, tablas y publicación sin reset/destrucción. Esto es evidencia con mocks y fuentes ejecutables, no una demostración de preservación de datos en OCI real.

**Rollback cloud automático no está implementado ni probado.** El snapshot y la reanudación durable no se presentan como rollback. No existe comando rollback que simule éxito. Para implementarlo se necesita restaurar y verificar el artefacto inmutable anterior, su código/workflow y despliegues, sin alterar claves/datos, con pruebas de fallo y aceptación nativa coordinada. Por tanto no se confirma que ese requisito esté cerrado.

Pendientes: ejecución real del runner con el archivo inmutable privado y sus acciones; aceptación nativa de permisos/recursos/runs/schedule y versiones servidas; calidad funcional de los agentes; publicación consultiva PROD. El perfil local LangGraph 1.2.16 heredado no acredita paridad nativa con el perfil 1.0.1 del plugin.

No se implementaron borrado, transferencia de estado/propiedad, migración de instalaciones combinadas ni rollback cloud automático. Update conserva snapshot; restaurar una revisión anterior necesita artefacto inmutable y procedimiento autorizado/verificado. No hay VM que descargue un artefacto privado: Governance viaja como código del paquete inmutable de hooks, sin PAT en Terraform, user-data o outputs.

Sin operaciones OCI, inferencia, actores pagados, cambios en Docker ni publicación de release. `.oci` no se abrió ni modificó. Solo este destino fue editado.
