import io
import json
from types import SimpleNamespace
import pytest
from ai_data_governance.receipts import ReceiptStore
from ai_data_governance.errors import AidpProvisionConflict


class StorageError(Exception):
    def __init__(self, status):
        self.status = status


class Objects:
    def __init__(self):
        self.rows = {}
        self.counter = 0

    def get_object(self, namespace, bucket, key):
        if key not in self.rows:
            raise StorageError(404)
        body, revision = self.rows[key]
        raw = io.BytesIO(body)
        return SimpleNamespace(data=SimpleNamespace(raw=raw, close=raw.close), headers={'etag': revision})

    def put_object(self, namespace, bucket, key, body, **kwargs):
        current = self.rows.get(key)
        if kwargs.get('if_none_match') == '*' and current:
            raise StorageError(412)
        if 'if_match' in kwargs and (not current or current[1] != kwargs['if_match']):
            raise StorageError(412)
        self.counter += 1
        revision = str(self.counter)
        self.rows[key] = body, revision
        return SimpleNamespace(headers={'etag': revision})


def store(objects, clock):
    return ReceiptStore(objects, 'namespace', 'artifacts', 'platform', 'workspace', clock=lambda: clock[0])


def test_exclusive_worker_receipt_cas_and_release():
    objects, clock = Objects(), [0]
    first, second = store(objects, clock), store(objects, clock)
    with first.acquire('operation'):
        with pytest.raises(AidpProvisionConflict, match='Another'):
            with second.acquire('operation'):
                pytest.fail('Duplicate worker entered')
        first.save({'operation_id': 'operation'}, None)
        receipt, revision = first.load()
        assert receipt == {'operation_id': 'operation'}
        with pytest.raises(AidpProvisionConflict, match='concurrently'):
            first.save({'changed': True}, 'stale-etag')
        assert first.load()[0] == receipt
    with second.acquire('operation'):
        second.save({**receipt, 'resumed': True}, revision)
        assert second.load()[0]['resumed'] is True


def test_expired_worker_is_fenced_after_another_owner_resumes():
    objects, clock = Objects(), [0]
    first, second = store(objects, clock), store(objects, clock)
    with first.acquire('operation'):
        clock[0] = 601
        with second.acquire('operation'):
            with pytest.raises(AidpProvisionConflict, match='ownership'):
                first.save({'late': True}, None)
            assert second.load() == (None, None)
