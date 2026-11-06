# Documentación de AIDP AI Data Governance

Estas guías describen el comportamiento del producto definido por el código y el manifiesto de Deploy Studio.

| Guía | Contenido |
| --- | --- |
| [Deploy Studio](deploy-studio.md) | Requisitos, recursos nuevos/existentes, parámetros e instalación. |
| [Operación](contracts.md) | Identidad, reintento, actualización, redeploy, rollback y estados. |
| [Memoria de agentes](agent-memory.md) | Autonomous, credencial ADMIN, asociación durable y límites. |
| [Desarrollo](development.md) | Entorno Python, estructura, validación y cambios de artefactos. |
| [Distribución](release.md) | Fuente inmutable, assets, hashes y compatibilidad de versiones. |

Las releases candidatas no equivalen a aceptación funcional en OCI. `TEST_PENDING` sigue requiriendo validación nativa de conversaciones, sesiones y ejecución del workflow.

Los [registros de auditoría, procedencia y validación](history/README.md) están separados de las instrucciones de operación; sus estados corresponden a cada versión registrada.
