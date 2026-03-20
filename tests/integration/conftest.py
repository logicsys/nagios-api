import os
import pytest
import requests
import time

API_BASE = os.environ.get('NAGIOS_API_URL', 'http://127.0.0.1:8080')

# Known test hosts/services defined in testhosts.cfg
TEST_HOST1 = 'testhost1'
TEST_HOST2 = 'testhost2'
TEST_HOSTGROUP = 'test-servers'
TEST_SVC_OK = 'TestService_OK'
TEST_SVC_WARN = 'TestService_WARN'
TEST_SVC_CRIT = 'TestService_CRIT'


class NagiosAPIClient:
    """Simple HTTP client for nagios-api."""

    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

    def get(self, endpoint, **kwargs):
        resp = self.session.get(f'{self.base_url}/{endpoint}', **kwargs)
        return resp.json()

    def post(self, endpoint, data=None, **kwargs):
        resp = self.session.post(
            f'{self.base_url}/{endpoint}',
            json=data or {},
            **kwargs
        )
        return resp.json()

    def wait_for_state_change(self, host, service=None, key='current_state',
                              expected=None, timeout=30):
        """Poll until a host/service attribute reaches an expected value."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if service:
                data = self.get(f'service/{host}')
                if data['success'] and service in data['content']:
                    val = data['content'][service].get(key)
                    if expected is None or str(val) == str(expected):
                        return data['content'][service]
            else:
                data = self.get(f'host/{host}')
                if data['success']:
                    val = data['content'].get(key)
                    if expected is None or str(val) == str(expected):
                        return data['content']
            time.sleep(2)
        raise TimeoutError(
            f'Timed out waiting for {host}/{service} {key}={expected}')


@pytest.fixture(scope='session')
def api():
    """Session-scoped API client."""
    client = NagiosAPIClient(API_BASE)
    # Verify API is reachable
    resp = client.get('state')
    assert resp['success'], f'API not ready: {resp}'
    return client
