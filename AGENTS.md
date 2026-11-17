# AI Data Governance

Python CLI/hooks and AIDP artifacts only: no portal, local login, HTTP server or administrative VM.
Read docs/migration-assessment.md and docs/tasks/current.md. Frozen provenance is recorded in provenance.json.
Never read, copy or modify .oci, commit credentials/state, or mutate cloud resources without scope authorization.
Run scripts/arch-preflight.ps1 before source changes and scripts/arch-postflight.ps1 afterward.
Preserve native identities, CAS receipts, operation IDs, permissions, two agents, eighteen tables and four workflow tasks.
Selected admin_user_ocid is not the signing operator. Validate domain, active user and effective AIDP roles at install and resume.
Deploy Studio integration and shared cloud operations belong to the coordinating chat; do not edit sibling repositories.
