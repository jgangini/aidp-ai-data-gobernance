# Desarrollo y validación

Python 3.11+, dependencias directas fijadas en `pyproject.toml` y `requirements.txt`; `requirements-lock.txt` registra exactamente el entorno de pruebas. Reusar el entorno; no cambiar versiones para aparentar paridad nativa. LangGraph local es 1.2.16 heredado del corte, no el perfil 1.0.1 del plugin: no se acredita compatibilidad nativa ni TEST por esa versión. La observación de versiones/bytes servidos requiere aceptación separada.

Arko se aplica a responsabilidades y contratos Python; su CLI instalado solo admite perfil fastapi-react, incompatible con este producto sin portal. No se inicializó ese perfil, no se creó servidor web y no se declara `arko check` aprobado. La ruta de validación del repositorio mantiene los contratos Python/CLI y de artefactos.

```powershell
./scripts/arch-preflight.ps1
.venv/Scripts/python.exe scripts/refresh_package.py
./scripts/arch-postflight.ps1
```

`refresh_package.py` solo actualiza hashes declarados para un candidato intencional; no convierte fixtures ni recibos en aceptación. No volver a ejecutar los scripts de extracción sobre una fuente ya modificada: son herramientas de procedencia de una única extracción desde Git, no sincronizadores de producto. La fuente congelada y cada archivo se registran en `provenance.json`.

Los tests importados ejercitan dominio, assembly, sintaxis ejecutable, permisos, inventario, entrega documental, lectura/reobservación de evidencia, persistencia y recuperación. Los nuevos tests verifican CLI, recibos CAS/fencing, instalación/resume y mantenimiento reversible sin ejecutar DDL/tasks/inferencia. Cubren backup inmutable/versionado, exactraw JSON, update parcial, refresh fallido, restore fallido y exitoso, acknowledgements perdidos, rechazo explícito frente a resultado incierto, idempotencia, revocación administrativa y corte tras un run nuevo. Terraform usa proveedores simulados para las cuatro combinaciones AIDP/bucket new/existing y rechazo de bindings inválidos. No invocan OCI ni modelos.

En Windows, usar un basetemp nuevo dentro de `.local`; los permisos del sandbox impidieron temporales/cleanup de pytest y build. Las ejecuciones con permisos locales adecuados conservan assertions y casos originales. No borrar temporales de otros procesos.

Graphify no está configurado; no se inicializa. No hay reglas Sentrux personalizadas. La referencia inicial de este destino vacío se conserva: el gate registra degradación al añadir todo el código extraído. Cero ciclos y cero god files no equivalen a un gate aprobado. Ver el resultado exacto y el resto de evidencias en `docs/tasks/current.md`; no recalibrar la referencia para ocultarlo.

CI ejecuta pytest, compilación Python y Terraform validate/test con mocks. Se comprobó el manifiesto con el parser Pydantic real de Deploy Studio. La ejecución del runner, roles/recursos/runs nativos, calidad de respuestas y publicación son gates distintos aún no ejecutados. El repositorio y sus nuevas candidatas son públicos; la instalación cloud y la persistencia efectiva de memoria no están aceptadas. El SDK de control plane es OCI 2.189.0, con lock actualizado; no se actualizan por analogía los paquetes nativos de los agentes.
