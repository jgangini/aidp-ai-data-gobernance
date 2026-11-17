import hashlib
import json
OCI_CREDENTIALS = ("AidpRuntime",)

def identity_hash(config):
    identity = [config.get(key) for key in ("tenancy", "user", "fingerprint")]
    if any(not isinstance(value, str) or not value for value in identity):
        raise RuntimeError("OCI runtime identity incomplete")
    return hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()

def shared_credential(credentials):
    """Choose once at deployment; an invalid preferred credential never triggers fallback."""
    for name in OCI_CREDENTIALS:
        matches = [item for item in credentials if item.get("displayName") == name
                   and (item.get("lifecycleState") or item.get("lifeCycleState") or item.get("state")) != "DELETED"]
        if not matches:
            continue
        if len(matches) != 1:
            raise RuntimeError("Duplicate shared OCI credentials")
        item = matches[0]
        if (item.get("type") or item.get("credentialType")) != "SECRET_TOKEN":
            raise RuntimeError("Shared OCI credential has an incompatible type")
        if (item.get("lifecycleState") or item.get("lifeCycleState") or item.get("state")) != "ACTIVE" or not (item.get("key") or item.get("id")):
            raise RuntimeError("Shared OCI credential is not ready")
        return item
    return None
