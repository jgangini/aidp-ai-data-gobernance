# AIDP AI Data Governance

Agentes de documentación y gobierno de datos para Oracle AI Data Platform. El producto se instala desde Deploy Studio en una plataforma nueva o existente, con el dominio y el administrador seleccionados en el formulario. No incluye portal web ni VM administrativa.

Repositorio canónico: [jgangini/aidp-ai-data-gobernance](https://github.com/jgangini/aidp-ai-data-gobernance). El nombre del repositorio usa **gobernance**; el identificador técnico del producto sigue siendo `aidp-ai-data-governance` y el paquete Python, `ai_data_governance`.

## Qué despliega

| Componente | Función |
| --- | --- |
| Agente documental | Genera y revisa documentación de metadatos dentro del workflow. |
| Agente de gobierno | Atiende consultas sobre el catálogo y los casos de gobierno con herramientas y límites explícitos. |
| Dieciocho tablas Delta | Conservan inventario, evidencias, documentación, ejecuciones y casos de gobierno en `oci_medallion.oci_artifacts`. |
| Workflow de cuatro tareas | Sincroniza inventario, documenta metadatos, los publica y replica el modelo del catálogo. |
| Recibos y copias de artefactos | Permiten reanudar operaciones y restaurar archivos propios con verificación SHA-256. |

El modelo OCI Generative AI se selecciona para los agentes de Governance. Los checkpoints usan el proxy de memoria administrado por AIDP, con identidades separadas para cada agente. El instalador crea o reutiliza Autonomous AI Lakehouse 26ai y habilita la memoria mediante el control plane de AIDP, con recibos para reanudar. El [contrato de memoria](docs/agent-memory.md) describe requisitos, evidencia técnica y límites de aceptación. Las tablas Delta del catálogo no sustituyen esa base de memoria.

## Instalación desde Deploy Studio

1. Selecciona un [tag de release inmutable](https://github.com/jgangini/aidp-ai-data-gobernance/releases) y la operación `install`.
2. Elige la plataforma nueva o indica la plataforma y el workspace existentes.
3. Selecciona el Identity Domain, un administrador elegible y el modelo OCI Generative AI.
4. Configura el bucket privado de artefactos y elige una Autonomous AI Lakehouse nueva o existente. La nueva usa el perfil 26ai/DW, cuatro ECPU y 1 TB.
5. Proporciona la contraseña ADMIN protegida cuando deba crearse o vincularse la base, revisa el plan y ejecuta el flujo autorizado. No se requiere wallet.

El operador firma las solicitudes OCI; seleccionar otro administrador no cambia esa identidad. Los recursos existentes se conservan como externos. Una instalación nueva asigna el rol elegido sólo durante su bootstrap inicial; reanudar no repone permisos revocados.

Para incorporar otros productos al mismo AIDP, utiliza `ai_data_platform_ocid` y el `workspace_key` verificado que devuelve el **post-apply final**. En una plataforma nueva, el valor inicial de Terraform para el workspace está vacío.

## Operación y recuperación

| Operación | Comportamiento |
| --- | --- |
| `install` | Instala el candidato y verifica sus recursos técnicos. |
| `resume` | Continúa la misma operación, fuente inmutable e identidad. |
| `update` / `redeploy` | Mantiene recursos e identidades y actualiza los artefactos propios. |
| `rollback` | Restaura los artefactos previos y refresca los agentes existentes. |

El rollback no revierte datasets, bases de datos ni infraestructura. Se bloquea ante revisiones ajenas, copias corruptas, cambios incompatibles de modelo o almacenamiento y nueva actividad que requiera conciliación de datos. Un update fallido que se restaura sigue devolviendo un fallo; no se presenta como una actualización exitosa.

## Desarrollo local

Se requiere Python 3.11 y `uv`. Desde la raíz del repositorio:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt
uv pip install --python .venv/Scripts/python.exe --no-deps -e .
.venv/Scripts/python.exe -m ai_data_governance.cli --help
.venv/Scripts/python.exe -m pytest tests -q
```

La validación del proyecto usa `scripts/arch-preflight.ps1` y `scripts/arch-postflight.ps1`; Terraform tiene pruebas con proveedores simulados. No se necesita acceso OCI para ejecutar las pruebas unitarias. Los hooks operativos requieren el contexto protegido de Deploy Studio y no deben ejecutarse contra una instalación real como prueba local.

## Estado y documentación

Las releases candidatas y sus pruebas locales no acreditan conversaciones reales ni aceptación funcional en OCI. El estado técnico mantiene `TEST_PENDING`; la publicación consultiva PROD requiere su aceptación correspondiente. Sentrux conserva el baseline inicial vacío y su gate sigue fallando con tres funciones complejas heredadas, sin ciclos ni archivos concentradores.

- [Contrato y operación](docs/contracts.md)
- [Memoria de agentes: implementación y límites](docs/agent-memory.md)
- [Releases, parámetros y hashes](docs/release.md)
- [Desarrollo y validación](docs/development.md)
- [Estado y evidencia de la tarea](docs/tasks/current.md)
- [Procedencia de las fuentes](provenance.json)

Las capacidades se extrajeron del commit congelado `3c82617fd298933995e954955841007253cc0985` de Starter Kits. La [evaluación de migración](docs/migration-assessment.md) conserva ese contexto histórico. Licencia [MIT](LICENSE).
