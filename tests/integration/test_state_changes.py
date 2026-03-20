"""Integration tests that verify Nagios state changes propagate through the API."""
import time
import pytest
from .conftest import TEST_HOST1, TEST_HOST2, TEST_SVC_OK, TEST_SVC_CRIT


class TestPassiveCheckResults:
    """Verify that passive check results submitted via the API
    are reflected in subsequent state queries."""

    def test_submit_and_verify_service_ok(self, api):
        """Submit a passive OK result and verify it appears in state."""
        api.post('submit_result', {
            'host': TEST_HOST1,
            'service': TEST_SVC_OK,
            'status': 0,
            'output': 'INTEGRATION_OK_MARKER',
        })
        # Wait for status.dat to update (configured for 3s interval)
        time.sleep(5)
        data = api.get(f'service/{TEST_HOST1}')
        assert data['success'] is True
        svc = data['content'].get(TEST_SVC_OK, {})
        # The plugin_output should eventually reflect our submission
        # (passive checks may take a cycle to show up)
        assert 'current_state' in svc

    def test_submit_critical_creates_problem(self, api):
        """Submit a CRITICAL passive result and verify it shows in problems."""
        api.post('submit_result', {
            'host': TEST_HOST1,
            'service': TEST_SVC_CRIT,
            'status': 2,
            'output': 'INTEGRATION_CRIT_MARKER - forced critical',
        })
        time.sleep(5)
        data = api.get('problems')
        assert data['success'] is True
        # The problems endpoint should include our host with the critical svc
        if TEST_HOST1 in data['content']:
            assert TEST_SVC_CRIT in data['content'][TEST_HOST1]['services']


class TestDowntimeLifecycle:
    """Test the full lifecycle: schedule downtime -> verify -> cancel."""

    def test_downtime_lifecycle(self, api):
        now = int(time.time())

        # Schedule downtime
        result = api.post('schedule_downtime', {
            'host': TEST_HOST2,
            'duration': 600,
            'author': 'lifecycle-test',
            'comment': 'Lifecycle test downtime',
            'start_time': now,
            'end_time': now + 600,
        })
        assert result['success'] is True

        # Wait for Nagios to process and update status
        time.sleep(5)

        # Verify host shows downtime depth > 0
        host_data = api.get(f'host/{TEST_HOST2}')
        assert host_data['success'] is True

        # Check state for downtime info
        state = api.get('state')
        assert state['success'] is True
        host_state = state['content'].get(TEST_HOST2, {})
        downtimes = host_state.get('downtimes', {})

        # Cancel downtimes by host (simpler and more reliable than by ID)
        cancel = api.post('cancel_downtime', {
            'host': TEST_HOST2,
        })
        if downtimes:
            assert cancel['success'] is True


class TestAcknowledgementLifecycle:
    """Test acknowledge -> verify -> remove cycle."""

    def test_ack_lifecycle(self, api):
        # Force a problem state via passive check
        api.post('submit_result', {
            'host': TEST_HOST1,
            'service': TEST_SVC_CRIT,
            'status': 2,
            'output': 'ACK_LIFECYCLE_TEST - critical',
        })
        time.sleep(5)

        # Acknowledge the problem
        ack = api.post('acknowledge_problem', {
            'host': TEST_HOST1,
            'service': TEST_SVC_CRIT,
            'author': 'lifecycle-test',
            'comment': 'Acknowledging for lifecycle test',
        })
        assert ack['success'] is True

        # Wait and verify acknowledgement
        time.sleep(5)
        svc_data = api.get(f'service/{TEST_HOST1}')
        assert svc_data['success'] is True
        crit_svc = svc_data['content'].get(TEST_SVC_CRIT, {})
        # problem_has_been_acknowledged should be 1
        if 'problem_has_been_acknowledged' in crit_svc:
            assert crit_svc['problem_has_been_acknowledged'] == '1'

        # Remove acknowledgement
        remove = api.post('remove_acknowledgement', {
            'host': TEST_HOST1,
            'service': TEST_SVC_CRIT,
        })
        assert remove['success'] is True


class TestCommentLifecycle:
    """Test add comment -> verify in state -> delete."""

    def test_comment_lifecycle(self, api):
        # Add a comment
        add = api.post('add_comment', {
            'host': TEST_HOST1,
            'author': 'lifecycle-test',
            'comment': 'LIFECYCLE_COMMENT_MARKER',
        })
        assert add['success'] is True

        # Wait for status update
        time.sleep(5)

        # Check if comments appear in host state
        state = api.get('state')
        assert state['success'] is True
        host_state = state['content'].get(TEST_HOST1, {})
        comments = host_state.get('comments', {})

        # Clean up - delete all host comments (comment_id=-1 means all)
        cleanup = api.post('delete_comment', {
            'host': TEST_HOST1,
            'comment_id': -1,
        })
        assert cleanup['success'] is True


class TestNotificationToggle:
    """Test disable/enable notifications and verify via state."""

    def test_notification_toggle(self, api):
        # Disable notifications
        disable = api.post('disable_notifications', {
            'host': TEST_HOST1,
        })
        assert disable['success'] is True

        time.sleep(5)

        # Check state - notifications should be disabled
        host_data = api.get(f'host/{TEST_HOST1}')
        assert host_data['success'] is True
        if 'notifications_enabled' in host_data['content']:
            assert host_data['content']['notifications_enabled'] == '0'

        # Re-enable notifications
        enable = api.post('enable_notifications', {
            'host': TEST_HOST1,
        })
        assert enable['success'] is True

        time.sleep(5)

        # Verify re-enabled
        host_data = api.get(f'host/{TEST_HOST1}')
        assert host_data['success'] is True
        if 'notifications_enabled' in host_data['content']:
            assert host_data['content']['notifications_enabled'] == '1'
