import threading
from unittest.mock import Mock
import pytest
from ai_data_governance.client import AidpClient
from ai_data_governance.native_client import NativeClient
from ai_data_governance.errors import AidpProvisionConflict


def test_raw_transport_preserves_json_whitespace_and_default_transport_stays_typed():
    client = object.__new__(AidpClient)
    client.base, client.signer = 'https://native.invalid', Mock()
    client._session_lock = threading.Lock()
    client._request_headers = Mock(return_value={})
    response = Mock(status_code=200, content=b' { "field" : 1 }\n', headers={'type': 'FILE'})
    response.json.return_value = {'field': 1}
    client.session = Mock()
    client.session.request.return_value = response
    raw, headers = client._request('GET', '/workspace', raw_response=True, include_headers=True)
    assert raw == b' { "field" : 1 }\n' and headers == {'type': 'FILE'}
    assert client._request('GET', '/workspace') == {'field': 1}


@pytest.mark.parametrize('body,headers', [(None, {}), ({'interpreted': True}, {}), (b'', {'type': 'FOLDER'})])
def test_raw_artifact_snapshot_rejects_unavailable_or_interpreted_content(body, headers):
    client = object.__new__(NativeClient)
    client._request = Mock(return_value=(body, headers))
    with pytest.raises(AidpProvisionConflict, match='raw file bytes'):
        client.read_artifact('workspace', '/Workspace/.artifact/ai_data_governance/file.json')
    assert client._request.call_args.kwargs['raw_response'] is True


def test_exact_artifact_writer_does_not_treat_reformatted_json_as_unchanged():
    client = object.__new__(NativeClient)
    original, target = b'{"field":1}', b'{\n  "field": 1\n}\n'
    client.read_artifact = Mock(side_effect=[original, target])
    client._request = Mock()
    assert client.write_artifact('workspace', '/owned.json', target) is True
    assert client._request.call_args.args == ('POST', '/workspaces/workspace/objects')
    assert client._request.call_args.kwargs['data'] == target
    assert client._request.call_args.kwargs['headers']['is-overwrite'] == 'true'


def test_exact_artifact_writer_skips_an_already_restored_file():
    client = object.__new__(NativeClient)
    client.read_artifact = Mock(return_value=b'{ "field": 1 }\n')
    client._request = Mock()
    assert client.write_artifact('workspace', '/owned.json', b'{ "field": 1 }\n') is False
    client._request.assert_not_called()
