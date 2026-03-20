"""Integration tests for the /availability endpoint.

These tests require Apache + Nagios CGI (avail.cgi) running in the container,
configured via --nagios-cgi-url on nagios-api startup.
"""
import time
import pytest
from .conftest import TEST_HOST1, TEST_HOST2, TEST_SVC_OK


class TestAvailabilityHost:
    def test_host_availability_default_period(self, api):
        """Fetch host availability with default 24h window."""
        data = api.get(f'availability/{TEST_HOST1}')
        assert data['success'] is True
        content = data['content']
        assert content['host'] == TEST_HOST1
        assert 'breakdown' in content
        assert 'log' in content
        assert 'start' in content
        assert 'end' in content
        assert content['end'] > content['start']

    def test_host_availability_with_period(self, api):
        """Fetch host availability with period shorthand."""
        data = api.get(f'availability/{TEST_HOST1}', params={'period': '24h'})
        assert data['success'] is True
        content = data['content']
        assert content['host'] == TEST_HOST1
        assert 'breakdown' in content

    def test_host_availability_7d_period(self, api):
        data = api.get(f'availability/{TEST_HOST1}', params={'period': '7d'})
        assert data['success'] is True

    def test_host_availability_30d_period(self, api):
        data = api.get(f'availability/{TEST_HOST1}', params={'period': '30d'})
        assert data['success'] is True

    def test_host_availability_custom_timestamps(self, api):
        """Fetch host availability with explicit start/end timestamps."""
        now = int(time.time())
        start = now - 3600  # 1 hour ago
        data = api.get(f'availability/{TEST_HOST1}',
                       params={'start': start, 'end': now})
        assert data['success'] is True
        content = data['content']
        assert content['start'] == start
        assert content['end'] == now


class TestAvailabilityService:
    def test_service_availability(self, api):
        """Fetch service availability."""
        data = api.get(f'availability/{TEST_HOST1}',
                       params={'service': TEST_SVC_OK, 'period': '24h'})
        assert data['success'] is True
        content = data['content']
        assert content['host'] == TEST_HOST1
        assert content['service'] == TEST_SVC_OK
        assert 'breakdown' in content


class TestAvailabilityBreakdown:
    def test_breakdown_has_states(self, api):
        """Breakdown should contain availability state categories."""
        data = api.get(f'availability/{TEST_HOST1}',
                       params={'service': TEST_SVC_OK, 'period': '24h'})
        assert data['success'] is True
        breakdown = data['content']['breakdown']
        # avail.cgi should return at least some state categories
        # (exact states depend on what Nagios has recorded)
        assert isinstance(breakdown, dict)


class TestAvailabilityErrors:
    def test_missing_hostname(self, api):
        data = api.get('availability')
        assert data['success'] is False

    def test_invalid_period(self, api):
        data = api.get(f'availability/{TEST_HOST1}',
                       params={'period': '99x'})
        assert data['success'] is False

    def test_start_after_end(self, api):
        now = int(time.time())
        data = api.get(f'availability/{TEST_HOST1}',
                       params={'start': now, 'end': now - 3600})
        assert data['success'] is False

    def test_invalid_timestamps(self, api):
        data = api.get(f'availability/{TEST_HOST1}',
                       params={'start': 'abc', 'end': 'xyz'})
        assert data['success'] is False
