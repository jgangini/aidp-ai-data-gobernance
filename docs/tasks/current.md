# Separación Governance

Implementación autorizada 2026-11-05. Fuente congelada `3c82617fd298933995e954955841007253cc0985`. Remoto privado verificado: `https://github.com/jgangini/aidp-ai_data_governance`, rama main. SHA candidato: pendiente de commit tras el último postflight; no hay release publicada.

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
- Regresión de precisión ISO/milisegundos: 45 tests del instalador y timestamp aprobados, incluyendo rechazo de runs realmente anteriores. No se relajaron assertions para obtener el pase.
- Terraform fmt/validate y cinco tests con proveedores simulados: aprobados tras el campo de operación final. Sin APIs OCI.
- Clase Pydantic real `DeploymentManifest` de CloudTechNext y `_extract_selected`: archivo staged final aprobado con los nueve campos, entrypoints, include_paths, restricciones de archivos y escáner del consumidor. `governance_operation` es un campo estático del formulario admitido; no una propiedad inventada del contrato.
- Wheel final construida en `.local/dist-reviewed-candidate/`; import desde directorio aislado y assembly repetido de 14 archivos aprobados. SHA-256: `3c19187cf438be9ad64423993201dd5759eb107791c489ab197a01b06535f40d`.
- Escaneo de 239 archivos staged y frontera de imports aprobado; git diff --cached --check sin errores después de normalización LF. `.gitattributes` fija LF para que Git/Windows no invaliden los hashes al clonar en Linux.
- Graphify no configurado, no inicializado. Arko solo guía Python; su perfil CLI fastapi-react no se impuso ni se declara aprobado.

## Gate arquitectónico y pendientes reales

Sentrux se ejecuta sobre una selección explícita de código versionado/no ignorado, excluyendo build, claves, caches y archivos privados. La referencia del destino vacío tenía cero funciones complejas y acoplamiento cero; añadir el producto hace fallar el gate. Última medición acotada final: calidad 0.7697 → 0.6968, acoplamiento 0 → 0.08, ciclos 0 y god files 0, funciones complejas 0 → 6. No hay reglas custom. La validación requerida **no está completa** mientras ese gate permanezca fallido; el candidato no se presenta como arquitectura aceptada ni release final. La coordinación debe revisar este cambio de alcance con evidencia antes de aprobar una referencia de producto.

Pendientes: ejecución real del runner con el archivo inmutable privado y sus acciones; aceptación nativa de permisos/recursos/runs/schedule y versiones servidas; calidad funcional de los agentes; publicación consultiva PROD. El perfil local LangGraph 1.2.16 heredado no acredita paridad nativa con el perfil 1.0.1 del plugin.

No se implementaron borrado, transferencia de estado/propiedad, migración de instalaciones combinadas ni rollback cloud automático. Update conserva snapshot; restaurar una revisión anterior necesita artefacto inmutable y procedimiento autorizado/verificado. No hay VM que descargue un artefacto privado: Governance viaja como código del paquete inmutable de hooks, sin PAT en Terraform, user-data o outputs.

Sin operaciones OCI, inferencia, actores pagados, cambios en Docker ni publicación de release. `.oci` no se abrió ni modificó. Solo este destino fue editado.
