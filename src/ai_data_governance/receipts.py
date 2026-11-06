"""Conditional Object Storage receipts and fenced, renewable operation ownership."""
from contextlib import contextmanager
import hashlib
import json
import re
import time
import uuid
from .errors import AidpProvisionConflict, AidpProvisionError


class ReceiptStore:
    def __init__(self, objects, namespace, bucket, platform, workspace, *, clock=time.time):
        self.objects, self.namespace, self.bucket = objects, namespace, bucket
        digest = hashlib.sha256((platform + ':' + workspace).encode()).hexdigest()
        self.prefix = '.control/ai_data_governance/installations/' + digest + '/'
        self.clock, self.token = clock, None

    def read(self, name):
        try:
            response = self.objects.get_object(self.namespace, self.bucket, self.prefix + name)
        except Exception as error:
            if getattr(error, 'status', None) == 404:
                return None, None
            raise AidpProvisionError('The durable Governance receipt cannot be read') from None
        try:
            body = response.data.raw.read(4 * 1024 * 1024 + 1)
            revision = response.headers.get('etag') or response.headers.get('ETag')
            if len(body) > 4 * 1024 * 1024 or not revision:
                raise AidpProvisionError('Invalid durable Governance receipt')
            return json.loads(body), revision
        finally:
            response.data.close()

    def write(self, name, value, revision):
        body = json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()
        if len(body) > 4 * 1024 * 1024:
            raise AidpProvisionError('Governance receipt exceeds its bound')
        try:
            response = self.objects.put_object(self.namespace, self.bucket, self.prefix + name, body,
                content_type='application/json', **({'if_match': revision} if revision else {'if_none_match': '*'}))
        except Exception as error:
            if getattr(error, 'status', None) == 412:
                raise AidpProvisionConflict('Governance receipt changed concurrently; observe before retry') from None
            raise AidpProvisionError('Governance receipt write outcome is uncertain; reconcile before retry') from None
        if not (response.headers.get('etag') or response.headers.get('ETag')):
            raise AidpProvisionError('Governance receipt write was not acknowledged with a revision')

    def heartbeat(self):
        lock, revision = self.read('lock.json')
        if not self.token or not lock or lock.get('token') != self.token or lock['expires'] <= self.clock():
            raise AidpProvisionConflict('Governance operation ownership expired or changed')
        self.write('lock.json', {**lock, 'expires': self.clock() + 600}, revision)

    @contextmanager
    def acquire(self, operation_id):
        lock, revision = self.read('lock.json')
        if lock and lock.get('expires', 0) > self.clock():
            raise AidpProvisionConflict('Another Governance worker owns the durable operation')
        token = str(uuid.uuid4())
        self.write('lock.json', {'operation_id': operation_id, 'token': token, 'expires': self.clock() + 600}, revision)
        self.token = token
        try:
            yield self
        finally:
            current, revision = self.read('lock.json')
            if current and current.get('token') == token:
                self.write('lock.json', {**current, 'expires': 0}, revision)
            self.token = None

    def load(self):
        return self.read('receipt.json')

    def save(self, receipt, revision):
        self.heartbeat()
        self.write('receipt.json', receipt, revision)

    def _artifact_name(self, digest):
        if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
            raise ValueError('An artifact SHA-256 is required')
        return self.prefix + 'artifacts/sha256/' + digest

    def get_artifact(self, digest):
        target = self._artifact_name(digest)
        try:
            response = self.objects.get_object(self.namespace, self.bucket, target)
        except Exception:
            raise AidpProvisionError('The immutable artifact backup cannot be read') from None
        try:
            body = response.data.raw.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024 or hashlib.sha256(body).hexdigest() != digest:
                raise AidpProvisionConflict('The immutable artifact backup hash differs')
            return body
        finally:
            response.data.close()

    def put_artifact(self, body):
        if not isinstance(body, bytes) or len(body) > 4 * 1024 * 1024:
            raise ValueError('Artifact backups require at most four MiB of bytes')
        digest = hashlib.sha256(body).hexdigest()
        self.heartbeat()
        try:
            self.objects.put_object(self.namespace, self.bucket, self._artifact_name(digest), body,
                content_type='application/octet-stream', if_none_match='*')
        except Exception:
            # A lost acknowledgement or a 412 is reconciled only by exact readback.
            pass
        if self.get_artifact(digest) != body:
            raise AidpProvisionConflict('The immutable artifact backup content differs')
        return digest
