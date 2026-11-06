"""Immutable candidate artifacts retain installation scope and verified bytes."""

import hashlib

import pytest

from ai_data_governance.errors import AidpProvisionConflict, AidpProvisionError
from ai_data_governance.receipts import ReceiptStore
from tests.test_receipts import Objects


class ScopedObjects(Objects):
    def __init__(self):
        super().__init__()
        self.calls = []

    def get_object(self, namespace, bucket, key):
        self.calls.append(('get', namespace, bucket, key))
        return super().get_object(namespace, bucket, (namespace, bucket, key))

    def put_object(self, namespace, bucket, key, body, **kwargs):
        self.calls.append(('put', namespace, bucket, key, kwargs))
        return super().put_object(namespace, bucket, (namespace, bucket, key), body, **kwargs)


def store(objects, *, namespace='namespace', bucket='artifacts', platform='platform', workspace='workspace', clock=None):
    return ReceiptStore(objects, namespace, bucket, platform, workspace, clock=clock or (lambda: 0))


def object_name(receipts, digest):
    return receipts.prefix + 'artifacts/sha256/' + digest


@pytest.mark.parametrize('body', [b'', b'Python source\n', bytes(range(256)), 'fuente documental con ñ'.encode()])
def test_artifact_roundtrip_uses_exact_bytes_conditional_write_and_readback(body):
    objects = ScopedObjects()
    receipts = store(objects)
    digest = hashlib.sha256(body).hexdigest()
    with receipts.acquire('operation'):
        returned = receipts.put_artifact(body)
    assert returned == digest
    assert receipts.get_artifact(digest) == body
    key = object_name(receipts, digest)
    writes = [call for call in objects.calls if call[0] == 'put' and call[3] == key]
    assert len(writes) == 1
    assert writes[0][1:3] == ('namespace', 'artifacts')
    assert writes[0][4]['if_none_match'] == '*'
    assert writes[0][4]['content_type'] == 'application/octet-stream'
    assert any(call[0] == 'get' and call[3] == key for call in objects.calls)
    assert objects.rows[('namespace', 'artifacts', key)][0] == body
    assert ('namespace', 'artifacts', receipts.prefix + 'receipt.json') not in objects.rows


def test_duplicate_conditional_write_accepts_only_the_identical_blob():
    objects = ScopedObjects()
    receipts = store(objects)
    with receipts.acquire('operation'):
        digest = receipts.put_artifact(b'candidate')
        key = ('namespace', 'artifacts', object_name(receipts, digest))
        original_revision = objects.rows[key][1]
        assert receipts.put_artifact(b'candidate') == digest
        assert objects.rows[key] == (b'candidate', original_revision)
        objects.rows[key] = (b'tampered', original_revision)
        with pytest.raises(AidpProvisionConflict):
            receipts.put_artifact(b'candidate')


def test_modified_stored_body_is_rejected_by_hash_before_use():
    objects = ScopedObjects()
    receipts = store(objects)
    digest = hashlib.sha256(b'original').hexdigest()
    objects.rows[('namespace', 'artifacts', object_name(receipts, digest))] = (b'altered', '1')
    with pytest.raises(AidpProvisionConflict):
        receipts.get_artifact(digest)


@pytest.mark.parametrize('changed_scope', [
    {'namespace': 'foreign-namespace'}, {'bucket': 'foreign-bucket'},
    {'platform': 'foreign-platform'}, {'workspace': 'foreign-workspace'},
])
def test_artifacts_never_fall_back_to_a_different_installation_or_storage_scope(changed_scope):
    objects = ScopedObjects()
    receipts = store(objects)
    with receipts.acquire('operation'):
        digest = receipts.put_artifact(b'owned-artifact')
    foreign = store(objects, **changed_scope)
    with pytest.raises(AidpProvisionError):
        foreign.get_artifact(digest)
    assert receipts.get_artifact(digest) == b'owned-artifact'


@pytest.mark.parametrize('digest', ['', 'a' * 63, 'A' * 64, '../receipt.json', None, b'a' * 64])
def test_invalid_digests_are_rejected_before_storage_access(digest):
    objects = ScopedObjects()
    with pytest.raises(ValueError):
        store(objects).get_artifact(digest)
    assert objects.calls == []


@pytest.mark.parametrize('body', [None, 'source', bytearray(b'candidate'), b'x' * (4 * 1024 * 1024 + 1)],
    ids=['none', 'text', 'bytearray', 'over-four-mib'])
def test_invalid_or_oversized_body_is_rejected_without_object_write(body):
    objects = ScopedObjects()
    receipts = store(objects)
    with receipts.acquire('operation'):
        before = list(objects.calls)
        with pytest.raises(ValueError):
            receipts.put_artifact(body)
        assert objects.calls == before


def test_four_mib_blob_is_permitted_but_oversized_readback_is_rejected():
    objects = ScopedObjects()
    receipts = store(objects)
    body = b'x' * (4 * 1024 * 1024)
    with receipts.acquire('operation'):
        digest = receipts.put_artifact(body)
    assert receipts.get_artifact(digest) == body
    objects.rows[('namespace', 'artifacts', object_name(receipts, digest))] = (body + b'x', '2')
    with pytest.raises(AidpProvisionConflict):
        receipts.get_artifact(digest)


@pytest.mark.parametrize('with_expired_lease', [False, True])
def test_artifact_write_requires_current_lease_before_mutating_storage(with_expired_lease):
    objects, clock = ScopedObjects(), [0]
    receipts = store(objects, clock=lambda: clock[0])
    if with_expired_lease:
        with receipts.acquire('operation'):
            clock[0] = 601
            with pytest.raises(AidpProvisionConflict):
                receipts.put_artifact(b'candidate')
    else:
        with pytest.raises(AidpProvisionConflict):
            receipts.put_artifact(b'candidate')
    assert not any(call[0] == 'put' and '/artifacts/sha256/' in call[3] for call in objects.calls)


class UncertainArtifactWrite(ScopedObjects):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode

    def put_object(self, namespace, bucket, key, body, **kwargs):
        if '/artifacts/sha256/' not in key:
            return super().put_object(namespace, bucket, key, body, **kwargs)
        if self.mode == 'absent':
            self.calls.append(('put', namespace, bucket, key, kwargs))
            raise TimeoutError('private-provider-detail')
        response = super().put_object(namespace, bucket, key, body, **kwargs)
        if self.mode == 'corrupt':
            self.rows[(namespace, bucket, key)] = (b'corrupt', 'altered')
            return response
        raise TimeoutError('private-provider-detail')


@pytest.mark.parametrize('mode,expected_error', [('stored', None), ('absent', AidpProvisionError), ('corrupt', AidpProvisionConflict)])
def test_unknown_or_acknowledged_write_requires_one_exact_readback(mode, expected_error):
    objects = UncertainArtifactWrite(mode)
    receipts = store(objects)
    body = b'immutable-candidate'
    digest = hashlib.sha256(body).hexdigest()
    with receipts.acquire('operation'):
        if expected_error:
            with pytest.raises(expected_error) as caught:
                receipts.put_artifact(body)
            assert 'private-provider-detail' not in str(caught.value)
        else:
            assert receipts.put_artifact(body) == digest
    key = object_name(receipts, digest)
    assert len([call for call in objects.calls if call[0] == 'get' and call[3] == key]) == 1
