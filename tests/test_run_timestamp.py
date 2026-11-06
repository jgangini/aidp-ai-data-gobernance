from datetime import datetime, timezone
import math
import pytest
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
