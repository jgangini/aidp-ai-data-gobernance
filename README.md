# AI Data Governance para AIDP

Paquete Python independiente con dos agentes, dieciocho tablas Delta y un workflow documental de cuatro tareas. Se instala desde Deploy Studio mediante CLI/hooks; no incluye portal, servidor HTTP ni VM administrativa.

El candidato procede del commit `3c82617fd298933995e954955841007253cc0985` de Starter Kits. [Procedencia](provenance.json), [contratos y operación](docs/contracts.md), [desarrollo y validación](docs/development.md), [estado de la migración](docs/tasks/current.md).

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt
uv pip install --python .venv/Scripts/python.exe --no-deps -e .
.venv/Scripts/python.exe -m ai_data_governance.cli --help
```

Los comandos operativos requieren contexto autorizado de Deploy Studio y credenciales protegidas del operador. No ejecutar hooks contra una instalación real como prueba local. Este candidato conserva `TEST_PENDING`: las pruebas locales y la instalación técnica no acreditan calidad funcional, ejecución actual ni publicación consultiva PROD.
