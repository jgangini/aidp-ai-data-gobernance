# Separación Governance: recuperación de artefactos

Fecha de trabajo: 2026-11-05 (America/Lima). Fuente congelada: `3c82617fd298933995e954955841007253cc0985`. Repositorio privado: https://github.com/jgangini/aidp-ai_data_governance, rama main.

El código anterior `868387f` y su cierre documental `174e7af` están subidos. [CI anterior 42141257951](https://github.com/jgangini/aidp-ai_data_governance/actions/runs/42141257951) aprobó 1.740 tests y cinco Terraform; esa evidencia no sustituye esta continuación. El contrato de recuperación está implementado y la suite local completa aprobó 1.836 tests. Commit `168273bbb8c4f143602aecea71a1d8552a995acf` subido; [CI 42146959451](https://github.com/jgangini/aidp-ai_data_governance/actions/runs/42146959451) aprobó 1.836 tests Python en 246.80 s, compilación y cinco tests Terraform. La [prerelease privada e inmutable v0.2.0-rc.1](https://github.com/jgangini/aidp-ai_data_governance/releases/tag/v0.2.0-rc.1) está publicada para su prueba real desde Deploy Studio; los cuatro assets descargados coinciden con sus hashes. Publicación autorizada por coordinación. Solo coordinación creará un AIDP y agregará los demás módulos sobre ese mismo; este chat no opera OCI.

## Contrato implementado

- Paquete Python/CLI/hooks y fuentes AIDP: dos agentes, dieciocho tablas y workflow de cuatro tareas. Sin portal, frontend, servidor HTTP, login local ni VM administrativa.
- Install conserva los gates nativos originales. Update/redeploy/rollback utilizan mantenimiento separado: no crean recursos, cambian permisos/credenciales, ejecutan DDL ni hacen POST jobRuns/inferencia.
- Antes de la primera mutación nativa se respaldan por bytes exactos los catorce assets y los dos descriptores de agente, con workflow/schedule, definiciones/despliegues e identidad/revisión previa. Blobs y snapshots por SHA-256, readback completo y referencia publicada por CAS. No se codifican programas en receipt.json.
- Historial versionado de referencias; nunca se borran copias automáticamente. Límite de cien generaciones antes de exigir revisión explícita de retención.
- Artefactos y agentes deben corresponder a las identidades registradas; no se adoptan recursos. Se rechazan nuevas/eliminadas rutas, cambios MODEL/NAMESPACE/STORAGE y cambios de modelo configurado antes de la primera pausa/escritura.
- Los writers se drenan tomando claves y estados de una sola observación; se comprueba de nuevo antes de escribir. Un writer nuevo no se incorpora silenciosamente a una barrera ya declarada.
- Refresh candidato y restore usan journals/scopes distintos. Resultado incierto se observa, sin reenviar a ciegas. Rechazo HTTP definitivo registrado admite Resume explícito.
- Fracaso parcial de update o refresh: restaura solamente bytes/definición previos y refresca esos agentes existentes; conserva datos, claves y el schedule previo exacto, incluido PAUSED.
- Restore fallido conserva el error original y un código adicional de restore; Resume continúa la misma copia y fase. La versión saludable efectiva se separa del candidato fallido.
- `update_failed_restored` sigue siendo fallo y sale 1; `restore_failed` sale 1; pendiente sale 3. `rollback_complete` sale 0 únicamente tras restauración y readbacks técnicos completos. No se convierte el update fallido en un éxito.
- Cutover propio con respuesta perdida: se reconcilia con intención durable, archivos exactos, refresh verificado y workflow objetivo. Runs legítimos nacidos después de esa activación no se cancelan ni revierten por confundirlos con actividad anterior.
- Administrador activo/roles efectivos se verifican cada vez. Solo install inicial new sin recibo propio puede conceder el rol seleccionado. Resume/update/rollback no reponen una revocación; recibo vacío o lookup fallido bloquean la concesión.

## Frontera exacta y límites

El rollback implementado cubre artefactos y refresh de control plane; no restaura datasets ni la infraestructura completa. Antes del cutover, cualquier run nuevo respecto a la barrera o una observación incompleta bloquea cambios de archivos/schedule; un run activo espera, un run nuevo confirmado exige conciliación de datos separada. Reactivar UNPAUSED puede permitir futuras ejecuciones: después de esa frontera no se intenta deshacer sus datos.

Se rechaza antes de sobrescribir si faltan bytes originales verificables, copias íntegras, definiciones completas, identidad/revisión propia o el contrato reversible de paths/modelo. Un snapshot corrupto o una edición ajena observada no se sobreescribe para forzar un pase. Workspace no tiene un CAS nativo observado: el lease protege los workers admitidos, no ediciones externas fuera de la ventana exclusiva de mantenimiento.

ACTIVE/timeUpdated y readback de archivos verifican el refresh técnico; no acreditan por sí solos una conversación, calidad funcional ni todos los bytes realmente servidos por el runtime. Si falta metadata necesaria se mantiene Pending con horario pausado. Ante rechazo de la API de refresh/restore se informa el fallo real; no se inventa un endpoint para reactivar un deployment histórico.

No se implementan borrado, transferencia de state/propiedad ni publicación consultiva PROD. Esas operaciones no son necesarias para la recuperación acotada y siguen fuera del alcance autorizado. No OCI, modelos, actores pagados, Docker ni release final ejecutados. `.oci` no se abrió ni modificó; solo este destino fue editado.

## Validación de esta continuación

- Preflight ejecutado: falla contra la referencia vacía original, que se conserva sin reset.
- Postflight estable `.local/postflight-recovery-final.txt`: **1.836 tests aprobados en 201.57 s** y compilación Python aprobada. Incluye recibos corruptos, guardas de identidades/formato, cutover incierto y writer race. El comando termina con error exclusivamente por el gate Sentrux frente al vacío, no por tests; no se declara postflight global aprobado.
- Pruebas focalizadas previas: 39 CLI, 26 store inmutable y 32 de recuperación/cutover/timestamps aprobaron; están incluidas en la suite, no son cobertura adicional sumable.
- Terraform fmt/validate y cinco tests con proveedores simulados aprobaron después de añadir rollback al campo de operación.
- Test cases incluyen: update parcial; restore fallido y éxito al Resume; refresh fallido; pérdida de ack de archivos y refresh; rechazo definitivo frente a envío incierto; múltiples generaciones; restores corruptos; conflicto de identidad/modelo/paths; JSON semánticamente igual con raw distinto; mezcla de revisiones; writes/tasks/permisos prohibidos; cutover con ack perdido y carrera de writer.
- Wheel independiente: imports aislados y hashes declarados aprobados; escaneo staged de 248 archivos aprobado. El parser/archive real del candidato seleccionó 129 archivos / 888.818 bytes con límites de 250 / 10 MiB; véase [contrato de release y parámetros exactos](../release.md). Inmutabilidad de releases habilitada y verificada mediante GitHub API; repositorio sigue privado.
- Evidencia del coordinador sobre `174e7af`: extracción real con límites efectivos **250 archivos / 10 MiB** seleccionó 124 archivos y 857.609 bytes. Importación de ambos entrypoints sobre solo ese árbol, Python 3.12 en imagen local ya existente y sin red/OCI, aprobó. Límite de archive GitHub: 100 MiB. No usar 64 MiB como contrato: fue un harness inicial corregido.
- Graphify no configurado, no inicializado. Arko orienta responsabilidades Python; su perfil fastapi-react no se impuso. No se declara arko check aprobado.
- Versiones nativas, roles/resources/runs/schedule y calidad de agentes siguen pendientes de aceptación coordinada. LangGraph local 1.2.16 heredado no acredita el perfil 1.0.1 ni paridad nativa.

## Sentrux: atribución y estado

No hay reglas custom ni excepciones inventadas. `.sentrux/initial-baseline.json` conserva la referencia de destino vacío; el gate se ejecuta sobre código versionado/no ignorado, sin caches/build/private state. La referencia no fue sustituida.

| Ámbito | Calidad mostrada | Acoplamiento redondeado | Complejas | Ciclos / god files |
| --- | --- | --- | --- | --- |
| Referencia vacía | 0.7697 | 0.00 | 0 | 0 / 0 |
| Capacidades congeladas extraídas | 0.6998 | 0.07 | 3 | 0 / 0 |
| Candidato anterior 868387f | 0.6968 | 0.08 | 6 | 0 / 0 |
| Recuperación actual | 0.7016 | 0.07 | 3 | 0 / 0 |

Las tres funciones complejas nuevas fueron eliminadas por responsabilidades reales: admisión y recibos; backup/compatibilidad; journal/refresh; estados de mantenimiento; parsing y binding del CLI. Ya no hay una función que mezcle esos pasos. Permanecen las tres heredadas del extracto congelado. Sin ciclos ni god files.

El gate general **continúa fallando** frente al vacío (0 → 3 y aumento de acoplamiento). Esta comparación no es una aprobación ni un reset. Frente al extracto la complejidad no aumenta y la calidad mostrada mejora aproximadamente 0.0018; corresponde a coordinación revisar esa evidencia para la aceptación de la arquitectura del producto.

## Evidencia local

`.local/preflight-recovery.txt`, `.local/recovery-first.txt`, `.local/artifact-recovery-2.txt`, `.local/recovery-integrated.txt`, `.local/cutover-recovery.txt`, `.local/sentrux-recovery-candidate.txt`, `.local/postflight-recovery-final.txt`. Los intentos intermedios quedan invalidados cuando cambió el código; no se presentan como cierre. SHA/CI y assets publicados registrados en [contrato de release](../release.md); el cierre posterior solo cambia documentación. El tag sigue fijado al código probado. No se ejecutó inferencia, actor pagado ni APPLY por este chat.
