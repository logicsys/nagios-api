"""Integration tests for read-only GET endpoints."""
import pytest
from .conftest import TEST_HOST1, TEST_HOST2, TEST_SVC_OK, TEST_SVC_WARN


class TestState:
    def test_state_returns_all_hosts(self, api):
        data = api.get('state')
        assert data['success'] is True
        assert TEST_HOST1 in data['content']
        assert TEST_HOST2 in data['content']

    def test_state_hosts_have_services(self, api):
        data = api.get('state')
        host1 = data['content'][TEST_HOST1]
        assert 'services' in host1
        assert TEST_SVC_OK in host1['services']

    def test_state_services_have_current_state(self, api):
        data = api.get('state')
        svc = data['content'][TEST_HOST1]['services'][TEST_SVC_OK]
        assert 'current_state' in svc


class TestObjects:
    def test_objects_lists_hosts(self, api):
        data = api.get('objects')
        assert data['success'] is True
        assert TEST_HOST1 in data['content']
        assert TEST_HOST2 in data['content']

    def test_objects_lists_services_per_host(self, api):
        data = api.get('objects')
        services = data['content'][TEST_HOST1]
        assert TEST_SVC_OK in services
        assert TEST_SVC_WARN in services


class TestHost:
    def test_host_found(self, api):
        data = api.get(f'host/{TEST_HOST1}')
        assert data['success'] is True
        assert 'current_state' in data['content']

    def test_host_has_services_list(self, api):
        data = api.get(f'host/{TEST_HOST1}')
        assert 'services' in data['content']
        assert TEST_SVC_OK in data['content']['services']

    def test_unknown_host(self, api):
        data = api.get('host/nonexistent_host_xyz')
        assert data['success'] is False

    def test_host_no_internal_attrs(self, api):
        data = api.get(f'host/{TEST_HOST1}')
        content = data['content']
        assert 'type' not in content
        assert 'essential_keys' not in content


class TestService:
    def test_service_found(self, api):
        data = api.get(f'service/{TEST_HOST1}')
        assert data['success'] is True
        assert TEST_SVC_OK in data['content']

    def test_service_has_state(self, api):
        data = api.get(f'service/{TEST_HOST1}')
        svc = data['content'][TEST_SVC_OK]
        assert 'current_state' in svc

    def test_unknown_host_service(self, api):
        data = api.get('service/nonexistent_host_xyz')
        assert data['success'] is False


class TestStatus:
    def test_status_has_info(self, api):
        data = api.get('status')
        assert data['success'] is True
        assert 'info' in data['content']
        assert 'version' in data['content']['info']

    def test_status_has_program(self, api):
        data = api.get('status')
        assert 'program' in data['content']
        assert 'nagios_pid' in data['content']['program']


class TestProblems:
    def test_problems_returns_success(self, api):
        data = api.get('problems')
        assert data['success'] is True
        # content is a dict of hosts with problem services
        assert isinstance(data['content'], dict)


class TestLog:
    def test_log_returns_entries(self, api):
        data = api.get('log')
        assert data['success'] is True
        # Log should have some entries from Nagios startup
        assert isinstance(data['content'], list)


class TestInvalidEndpoints:
    def test_unknown_verb(self, api):
        data = api.get('totally_fake_endpoint')
        assert data['success'] is False

    def test_error_does_not_echo_verb(self, api):
        data = api.get('secret_verb_xyz')
        assert data['success'] is False
        assert 'secret_verb_xyz' not in data['content']
