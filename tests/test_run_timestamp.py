from datetime import datetime, timezone
import math
import pytest
from unittest.mock import Mock
from ai_data_governance.deployment_refresh import DeploymentRefresh
from ai_data_governance.errors import AidpProvisionPending
from tests.domain.test_ai_dg_deploy_studio_install import fixture, Pending


@pytest.mark.parametrize('earlier_microseconds', [0, 1, 1000])
def test_lost_ack_compares_timestamp_precision_without_admitting_earlier_runs(earlier_microseconds):
    owner, manifest, installer = fixture()
    at = datetime(2026, 11, 5, 12, 0, 0, 123456, tzinfo=timezone.utc)
    observed = (at.timestamp() - earlier_microseconds / 1_000_000) * 1000
    observed = math.nextafter(observed, -math.inf)
    owner._list = lambda *args, **kwargs: [{'key': 'run-1', 'startTime': observed}]
    installer.resources['workflow_key'] = 'workflow'
    recorded = {'submitted_at': at.isoformat()}
    if earlier_microseconds:
        with pytest.raises(Pending, match='uncertain'):
            installer.reconcile_run_key(recorded)
        assert 'key' not in recorded
    else:
        assert installer.reconcile_run_key(recorded) == 'run-1'


@pytest.mark.parametrize('earlier_microseconds', [0, 1, 1000])
def test_deployment_refresh_uses_the_same_precision_boundary(earlier_microseconds):
    owner, manifest, _ = fixture()
    at = datetime(2026, 11, 5, 12, 0, 0, 123456, tzinfo=timezone.utc)
    journal = {'documentary': {'submitted_at': at.isoformat()}}
    refresh = DeploymentRefresh(owner, 'workspace', manifest, journal, Mock(), 'restore')
    timestamp = math.nextafter((at.timestamp() - earlier_microseconds / 1_000_000) * 1000, -math.inf)
    refresh._unique = Mock(return_value={'key': 'deployment', 'lifecycleState': 'ACTIVE', 'timeUpdated': timestamp})
    if earlier_microseconds:
        with pytest.raises(AidpProvisionPending):
            refresh._verified('documentary')
    else:
        refresh._verified('documentary')
        assert manifest['resources']['documentary_deployment_key'] == 'deployment'
