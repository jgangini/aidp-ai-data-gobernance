# Desarrollo y validación

## Entorno

El paquete requiere Python 3.11 o posterior. Las dependencias directas se declaran en `pyproject.toml` y `requirements.txt`; `requirements-lock.txt` fija el entorno de validación.

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt
uv pip install --python .venv/Scripts/python.exe --no-deps -e .
.venv/Scripts/python.exe -m ai_data_governance.cli --help
```

La CLI instalada también está disponible como `aidp-governance`. Los comandos operativos requieren contexto y credenciales protegidos de Deploy Studio; `--help` y los tests unitarios no ejecutan una instalación OCI.

## Estructura del código

| Ubicación | Responsabilidad |
| --- | --- |
| `cli.py` | Contexto, validación de bindings y resultado del runner. |
| `lifecycle.py`, `deploy_studio_install.py` | Admisión y fases de instalación. |
| `managed_memory.py`, `receipts.py` | Asociación de memoria y persistencia condicional con lease. |
| `maintenance.py`, `artifact_backups.py`, `deployment_refresh.py` | Mantenimiento y recuperación de artefactos. |
| `governance_*`, `documentary_*` | Grafos, estado, nodos y runtime de agentes. |
| `aidp/manifest.json`, `package/lab.json` | Recursos nativos, fuentes y hashes del paquete. |
| `terraform/` | Recursos, manifiesto de Deploy Studio y hooks. |
| `tests/`, `terraform/tests/` | Regresiones Python y contratos Terraform con mocks. |

Las rutas Python de la tabla son relativas a `src/ai_data_governance/`. El producto no necesita FastAPI/React ni un servidor web para instalarse.

## Flujo de validación

Antes de cambios de código o configuración, ejecuta preflight; después del cambio final, postflight:

```powershell
./scripts/arch-preflight.ps1
./scripts/arch-postflight.ps1
```

Postflight ejecuta el gate Sentrux, pytest y compilación Python. Para Terraform:

```powershell
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
terraform -chdir=terraform test
```

Los tests Terraform usan proveedores simulados. `init` prepara los proveedores declarados; no autoriza apply ni cambios de versión. Una comprobación Python focalizada puede ejecutarse con `.venv/Scripts/python.exe -m pytest <archivo> -q`; no reemplaza el postflight final cuando corresponde.

En Windows usa un basetemp nuevo dentro de `.local` si el entorno restringe los temporales. No borres temporales ajenos ni cambies assertions para obtener un pase.

## Cambiar programas distribuidos

Mantén como fuente los módulos Python importables y los descriptores declarados. El assembly genera programas deterministas; no se genera código mediante el modelo.

Si modificas intencionalmente un archivo declarado en `package/lab.json`, actualiza sus hashes con `.venv/Scripts/python.exe scripts/refresh_package.py` y valida sintaxis, bundle y pruebas del flujo afectado. No refresques hashes para ocultar una discrepancia no investigada.

Preserva identidades, condiciones CAS, límites de efectos y controles de datos. Una evaluación portable usa los hooks/checkpointer de `factories.py`; no reemplaza el adaptador nativo ni demuestra persistencia Oracle.

## Alcance de las comprobaciones

La CI ejecuta pytest, compilación y Terraform fmt/validate/test. Los tests cubren permisos, bindings, assembly, inventario, entrega documental, memoria, recibos, incertidumbre y restauración; no invocan OCI ni modelos reales.

Sentrux tiene un gate vigente fallido frente al baseline inicial conservado. No se recalibra para ocultar degradaciones; cero ciclos no significa gate aprobado. No hay reglas custom. Graphify no está configurado.

Las versiones del entorno local y de los paquetes nativos son contratos distintos. Cambiar el SDK del runner no acredita paridad del runtime de agentes. Los tests locales no prueban conversaciones, schedule real ni persistencia de sesiones; la instalación termina en `TEST_PENDING` y esos resultados requieren aceptación funcional separada.

Los [registros de validación](history/release-evidence.md) contienen resultados por versión; las herramientas de procedencia no son sincronizadores de producto.
