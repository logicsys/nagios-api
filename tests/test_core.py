import os
import pytest
from nagios.core import (
    Nagios, NagiosObject, Host, Service, Comment, Downtime, Info, Program,
)

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
STATUS_FILE = os.path.join(FIXTURES, 'status.dat')


@pytest.fixture
def nagios():
    return Nagios(STATUS_FILE)


# --- Nagios parsing ---

class TestNagiosParsing:
    def test_hosts_parsed(self, nagios):
        assert 'web01' in nagios.hosts
        assert 'db01' in nagios.hosts
        assert len(nagios.hosts) == 2

    def test_services_parsed(self, nagios):
        assert 'web01' in nagios.services
        assert 'HTTP' in nagios.services['web01']
        assert 'SSH' in nagios.services['web01']
        assert 'db01' in nagios.services
        assert 'MySQL' in nagios.services['db01']

    def test_comments_parsed(self, nagios):
        assert 1 in nagios.comments
        assert 2 in nagios.comments
        assert len(nagios.comments) == 2

    def test_downtimes_parsed(self, nagios):
        assert 10 in nagios.downtimes
        assert len(nagios.downtimes) == 1

    def test_info_parsed(self, nagios):
        assert nagios.info.version == '4.4.6'
        assert nagios.info.created == '1609459200'

    def test_program_parsed(self, nagios):
        assert nagios.program.nagios_pid == '12345'
        assert nagios.program.enable_notifications == '1'


# --- Host ---

class TestHost:
    def test_host_state(self, nagios):
        assert nagios.hosts['web01'].current_state == '0'
        assert nagios.hosts['db01'].current_state == '1'

    def test_host_plugin_output(self, nagios):
        assert 'PING OK' in nagios.hosts['web01'].plugin_output

    def test_host_has_services_attached(self, nagios):
        web01 = nagios.hosts['web01']
        assert 'HTTP' in web01.services
        assert 'SSH' in web01.services

    def test_host_has_comment_attached(self, nagios):
        web01 = nagios.hosts['web01']
        assert 1 in web01.comments

    def test_host_has_downtime_attached(self, nagios):
        db01 = nagios.hosts['db01']
        assert 10 in db01.downtimes

    def test_host_for_json_includes_services(self, nagios):
        result = nagios.hosts['web01'].for_json()
        assert 'services' in result
        assert 'HTTP' in result['services']

    def test_host_for_json_includes_comments(self, nagios):
        result = nagios.hosts['web01'].for_json()
        assert 'comments' in result
        assert 1 in result['comments']

    def test_host_for_json_includes_downtimes(self, nagios):
        result = nagios.hosts['db01'].for_json()
        assert 'downtimes' in result
        assert 10 in result['downtimes']


# --- Service ---

class TestService:
    def test_service_state(self, nagios):
        http = nagios.services['web01']['HTTP']
        assert http.current_state == '0'

    def test_service_critical(self, nagios):
        ssh = nagios.services['web01']['SSH']
        assert ssh.current_state == '2'
        assert ssh.problem_has_been_acknowledged == '1'

    def test_service_has_comment_attached(self, nagios):
        ssh = nagios.services['web01']['SSH']
        assert 2 in ssh.comments

    def test_service_for_json(self, nagios):
        http = nagios.services['web01']['HTTP']
        result = http.for_json()
        assert result['current_state'] == '0'
        assert 'comments' in result
        assert 'downtimes' in result


# --- Comment ---

class TestComment:
    def test_comment_fields(self, nagios):
        c = nagios.comments[1]
        assert c.comment_id == 1
        assert c.author == 'admin'
        assert c.comment_data == 'Host looks good'
        assert c.host == 'web01'

    def test_comment_for_json(self, nagios):
        result = nagios.comments[2].for_json()
        assert result['comment_id'] == 2
        assert result['author'] == 'oncall'


# --- Downtime ---

class TestDowntime:
    def test_downtime_fields(self, nagios):
        d = nagios.downtimes[10]
        assert d.downtime_id == 10
        assert d.author == 'admin'
        assert d.comment == 'Scheduled maintenance'
        assert d.host == 'db01'
        assert d.duration == '3600'

    def test_downtime_for_json(self, nagios):
        result = nagios.downtimes[10].for_json()
        assert result['downtime_id'] == 10
        assert result['author'] == 'admin'
        assert result['fixed'] == '1'


# --- Performance data parsing ---

class TestPerformanceData:
    def test_host_performance_data(self, nagios):
        pd = nagios.hosts['web01'].performance_data
        assert isinstance(pd, dict)
        # Values with unit suffixes (e.g. "0.50ms") stay as strings
        assert pd['rta'] == '0.50ms'
        assert pd['pl'] == '0%'

    def test_service_performance_data(self, nagios):
        http = nagios.services['web01']['HTTP']
        pd = http.performance_data
        assert isinstance(pd, dict)
        assert pd['time'] == '0.010s'
        assert pd['size'] == '1234B'

    def test_empty_performance_data(self, nagios):
        ssh = nagios.services['web01']['SSH']
        assert ssh.performance_data == {}


# --- NagiosObject ---

class TestNagiosObject:
    def test_for_json_returns_essential_keys(self):
        obj = NagiosObject({'host_name': 'test', 'extra': 'data'})
        obj.essential_keys = ['host_name']
        result = obj.for_json()
        assert result == {'host_name': 'test'}

    def test_for_json_missing_key_returns_none(self):
        obj = NagiosObject({})
        obj.essential_keys = ['missing']
        result = obj.for_json()
        assert result == {'missing': None}


# --- host_or_service ---

class TestHostOrService:
    def test_returns_host(self, nagios):
        result = nagios.host_or_service('web01')
        assert isinstance(result, Host)

    def test_returns_service(self, nagios):
        result = nagios.host_or_service('web01', 'HTTP')
        assert isinstance(result, Service)

    def test_unknown_host_returns_none(self, nagios):
        assert nagios.host_or_service('nonexistent') is None

    def test_unknown_service_returns_none(self, nagios):
        assert nagios.host_or_service('web01', 'FAKE') is None


# --- for_json (top-level) ---

class TestNagiosForJson:
    def test_for_json_has_all_hosts(self, nagios):
        result = nagios.for_json()
        assert 'web01' in result
        assert 'db01' in result

    def test_for_json_nested_structure(self, nagios):
        result = nagios.for_json()
        web01 = result['web01']
        assert 'services' in web01
        assert 'comments' in web01
        assert 'downtimes' in web01


# --- Empty state ---

class TestEmptyNagios:
    def test_empty_init(self):
        n = Nagios()
        assert n.hosts == {}
        assert n.services == {}
        assert n.comments == {}
        assert n.downtimes == {}
