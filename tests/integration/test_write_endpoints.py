"""Integration tests for write (POST) endpoints that send commands to Nagios."""
import time
import pytest
from .conftest import (
    TEST_HOST1, TEST_HOST2, TEST_HOSTGROUP,
    TEST_SVC_OK, TEST_SVC_WARN, TEST_SVC_CRIT,
)


class TestSubmitResult:
    """Test submitting passive check results."""

    def test_submit_host_result(self, api):
        data = api.post('submit_result', {
            'host': TEST_HOST1,
            'status': 0,
            'output': 'Integration test - host OK',
        })
        assert data['success'] is True

    def test_submit_service_result(self, api):
        data = api.post('submit_result', {
            'host': TEST_HOST1,
            'service': TEST_SVC_OK,
            'status': 0,
            'output': 'Integration test - service OK',
        })
        assert data['success'] is True

    def test_submit_result_missing_host(self, api):
        data = api.post('submit_result', {
            'status': 0,
            'output': 'No host',
        })
        assert data['success'] is False

    def test_submit_result_unknown_host(self, api):
        data = api.post('submit_result', {
            'host': 'nonexistent_host_xyz',
            'status': 0,
            'output': 'Bad host',
        })
        assert data['success'] is False


class TestScheduleDowntime:
    """Test scheduling and cancelling downtime."""

    def test_schedule_host_downtime(self, api):
        now = int(time.time())
        data = api.post('schedule_downtime', {
            'host': TEST_HOST2,
            'duration': 300,
            'author': 'integration-test',
            'comment': 'Testing host downtime',
            'start_time': now,
            'end_time': now + 300,
        })
        assert data['success'] is True

    def test_schedule_service_downtime(self, api):
        now = int(time.time())
        data = api.post('schedule_downtime', {
            'host': TEST_HOST1,
            'service': TEST_SVC_OK,
            'duration': 300,
            'author': 'integration-test',
            'comment': 'Testing service downtime',
            'start_time': now,
            'end_time': now + 300,
        })
        assert data['success'] is True

    def test_schedule_downtime_missing_host(self, api):
        now = int(time.time())
        data = api.post('schedule_downtime', {
            'duration': 300,
            'author': 'test',
            'comment': 'No host',
            'start_time': now,
            'end_time': now + 300,
        })
        assert data['success'] is False


class TestCancelDowntime:
    def test_cancel_downtime_nonexistent_id(self, api):
        data = api.post('cancel_downtime', {
            'downtime_id': 999999,
        })
        # Should succeed (Nagios accepts the command even if ID doesn't exist)
        # or fail gracefully
        assert isinstance(data['success'], bool)


class TestScheduleHostgroupDowntime:
    def test_schedule_hostgroup_downtime(self, api):
        now = int(time.time())
        data = api.post('schedule_hostgroup_downtime', {
            'hostgroup': TEST_HOSTGROUP,
            'duration': 300,
            'author': 'integration-test',
            'comment': 'Testing hostgroup downtime',
            'start_time': now,
            'end_time': now + 300,
        })
        assert data['success'] is True


class TestNotifications:
    def test_disable_host_notifications(self, api):
        data = api.post('disable_notifications', {
            'host': TEST_HOST1,
        })
        assert data['success'] is True

    def test_enable_host_notifications(self, api):
        data = api.post('enable_notifications', {
            'host': TEST_HOST1,
        })
        assert data['success'] is True

    def test_disable_service_notifications(self, api):
        data = api.post('disable_notifications', {
            'host': TEST_HOST1,
            'service': TEST_SVC_OK,
        })
        assert data['success'] is True

    def test_enable_service_notifications(self, api):
        data = api.post('enable_notifications', {
            'host': TEST_HOST1,
            'service': TEST_SVC_OK,
        })
        assert data['success'] is True

    def test_disable_host_and_services_notifications(self, api):
        data = api.post('disable_notifications', {
            'host': TEST_HOST1,
            'services_too': True,
        })
        assert data['success'] is True

    def test_enable_host_and_services_notifications(self, api):
        data = api.post('enable_notifications', {
            'host': TEST_HOST1,
            'services_too': True,
        })
        assert data['success'] is True

    def test_notifications_unknown_host(self, api):
        data = api.post('disable_notifications', {
            'host': 'nonexistent_host_xyz',
        })
        assert data['success'] is False


class TestChecks:
    def test_disable_host_checks(self, api):
        data = api.post('disable_checks', {
            'host': TEST_HOST2,
        })
        assert data['success'] is True

    def test_enable_host_checks(self, api):
        data = api.post('enable_checks', {
            'host': TEST_HOST2,
        })
        assert data['success'] is True

    def test_disable_service_checks(self, api):
        data = api.post('disable_checks', {
            'host': TEST_HOST1,
            'service': TEST_SVC_OK,
        })
        assert data['success'] is True

    def test_enable_service_checks(self, api):
        data = api.post('enable_checks', {
            'host': TEST_HOST1,
            'service': TEST_SVC_OK,
        })
        assert data['success'] is True

    def test_disable_host_and_services_checks(self, api):
        data = api.post('disable_checks', {
            'host': TEST_HOST2,
            'services_too': True,
        })
        assert data['success'] is True

    def test_enable_host_and_services_checks(self, api):
        data = api.post('enable_checks', {
            'host': TEST_HOST2,
            'services_too': True,
        })
        assert data['success'] is True


class TestScheduleCheck:
    def test_schedule_service_check(self, api):
        data = api.post('schedule_check', {
            'host': TEST_HOST1,
            'service': TEST_SVC_OK,
        })
        assert data['success'] is True

    def test_schedule_host_check(self, api):
        data = api.post('schedule_check', {
            'host': TEST_HOST1,
        })
        assert data['success'] is True

    def test_schedule_forced_check(self, api):
        data = api.post('schedule_check', {
            'host': TEST_HOST1,
            'service': TEST_SVC_OK,
            'forced': True,
        })
        assert data['success'] is True

    def test_schedule_host_and_all_services(self, api):
        data = api.post('schedule_check', {
            'host': TEST_HOST1,
            'all_services': True,
        })
        assert data['success'] is True


class TestAcknowledge:
    def test_acknowledge_host_problem(self, api):
        # First submit a critical result to create a problem
        api.post('submit_result', {
            'host': TEST_HOST2,
            'status': 1,
            'output': 'Integration test - host DOWN for ack test',
        })
        # Give Nagios a moment to process
        time.sleep(3)

        data = api.post('acknowledge_problem', {
            'host': TEST_HOST2,
            'author': 'integration-test',
            'comment': 'Acking for test',
        })
        assert data['success'] is True

    def test_remove_host_acknowledgement(self, api):
        data = api.post('remove_acknowledgement', {
            'host': TEST_HOST2,
        })
        assert data['success'] is True

    def test_acknowledge_service_problem(self, api):
        # Submit a critical result for the service
        api.post('submit_result', {
            'host': TEST_HOST1,
            'service': TEST_SVC_CRIT,
            'status': 2,
            'output': 'Integration test - CRITICAL for ack test',
        })
        time.sleep(3)

        data = api.post('acknowledge_problem', {
            'host': TEST_HOST1,
            'service': TEST_SVC_CRIT,
            'author': 'integration-test',
            'comment': 'Acking service for test',
        })
        assert data['success'] is True

    def test_remove_service_acknowledgement(self, api):
        data = api.post('remove_acknowledgement', {
            'host': TEST_HOST1,
            'service': TEST_SVC_CRIT,
        })
        assert data['success'] is True


class TestComments:
    def test_add_host_comment(self, api):
        data = api.post('add_comment', {
            'host': TEST_HOST1,
            'author': 'integration-test',
            'comment': 'Integration test host comment',
        })
        assert data['success'] is True

    def test_add_service_comment(self, api):
        data = api.post('add_comment', {
            'host': TEST_HOST1,
            'service': TEST_SVC_OK,
            'author': 'integration-test',
            'comment': 'Integration test service comment',
        })
        assert data['success'] is True

    def test_add_comment_missing_host(self, api):
        data = api.post('add_comment', {
            'author': 'test',
            'comment': 'No host',
        })
        assert data['success'] is False

    def test_delete_all_host_comments(self, api):
        """Use comment_id=-1 to delete all host comments."""
        data = api.post('delete_comment', {
            'host': TEST_HOST1,
            'comment_id': -1,
        })
        assert data['success'] is True

    def test_delete_nonexistent_comment(self, api):
        data = api.post('delete_comment', {
            'host': TEST_HOST1,
            'comment_id': 999999,
        })
        # Should succeed (Nagios accepts the command even if ID doesn't exist)
        assert data['success'] is True


class TestRawCommand:
    def test_allowed_raw_command(self, api):
        """Test sending an allowed raw command."""
        now = int(time.time())
        data = api.post('raw_command', {
            'command': f'PROCESS_HOST_CHECK_RESULT;{TEST_HOST1};0;OK via raw command',
        })
        assert data['success'] is True

    def test_disallowed_raw_command(self, api):
        """Test that disallowed commands are rejected."""
        data = api.post('raw_command', {
            'command': 'SHUTDOWN_PROGRAM',
        })
        assert data['success'] is False

    def test_raw_command_missing(self, api):
        data = api.post('raw_command', {})
        assert data['success'] is False


class TestRestartNagios:
    def test_get_restart_rejected(self, api):
        """GET on restart_nagios should be rejected (CSRF protection)."""
        data = api.get('restart_nagios')
        assert data['success'] is False
        assert 'POST' in data['content']

    def test_post_restart(self, api):
        """POST restart should succeed and Nagios should come back."""
        data = api.post('restart_nagios')
        assert data['success'] is True
        # Give Nagios time to restart
        time.sleep(5)
        # Verify API still works after restart
        state = api.get('state')
        assert state['success'] is True


class TestMethodEnforcement:
    def test_post_only_endpoints_reject_get(self, api):
        """Endpoints that require POST should not work with GET."""
        post_endpoints = [
            'schedule_downtime', 'cancel_downtime',
            'disable_notifications', 'enable_notifications',
            'disable_checks', 'enable_checks',
            'submit_result', 'acknowledge_problem',
            'remove_acknowledgement', 'add_comment',
            'delete_comment', 'schedule_check',
            'raw_command',
        ]
        for endpoint in post_endpoints:
            data = api.get(endpoint)
            assert data['success'] is False, \
                f'GET /{endpoint} should have failed but succeeded'
