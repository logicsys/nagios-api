import os
import time
import pytest
from unittest.mock import patch, MagicMock

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
AVAIL_HTML = os.path.join(FIXTURES, 'avail_response.html')


@pytest.fixture
def avail_html():
    with open(AVAIL_HTML, 'r') as f:
        return f.read()


class TestParseAvailHtml:
    def test_parses_breakdown(self, avail_html):
        from nagios.availability import _parse_avail_html
        result = _parse_avail_html(avail_html)
        breakdown = result['breakdown']

        assert 'OK' in breakdown
        assert 'CRITICAL' in breakdown
        assert 'WARNING' in breakdown
        assert 'UNKNOWN' in breakdown
        assert 'Undetermined' in breakdown

    def test_ok_total_values(self, avail_html):
        from nagios.availability import _parse_avail_html
        result = _parse_avail_html(avail_html)
        ok_total = result['breakdown']['OK']['Total']

        assert ok_total['total_pct'] == '99.861%'
        assert ok_total['known_pct'] == '99.896%'
        assert '23d 23h 30m 0s' in ok_total['time']

    def test_critical_total_values(self, avail_html):
        from nagios.availability import _parse_avail_html
        result = _parse_avail_html(avail_html)
        crit_total = result['breakdown']['CRITICAL']['Total']

        assert crit_total['total_pct'] == '0.014%'

    def test_undetermined_no_known_pct(self, avail_html):
        from nagios.availability import _parse_avail_html
        result = _parse_avail_html(avail_html)
        undet = result['breakdown']['Undetermined']

        for entry in undet.values():
            assert 'known_pct' not in entry

    def test_parses_service_log(self, avail_html):
        from nagios.availability import _parse_avail_html
        result = _parse_avail_html(avail_html)
        log_entries = result['log']

        assert len(log_entries) == 2
        assert log_entries[0]['state_type'] == 'SERVICE CRITICAL (HARD)'
        assert log_entries[0]['info'] == 'Connection refused'
        assert log_entries[1]['state_type'] == 'SERVICE OK (HARD)'

    def test_empty_html_returns_empty(self):
        from nagios.availability import _parse_avail_html
        result = _parse_avail_html('<html><body></body></html>')

        assert result['breakdown'] == {}
        assert result['log'] == []


class TestFetchAvailability:
    @patch('nagios.availability.requests.get')
    def test_fetch_calls_cgi(self, mock_get, avail_html):
        from nagios.availability import fetch_availability, _cache
        _cache.clear()

        mock_resp = MagicMock()
        mock_resp.text = avail_html
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = fetch_availability(
            'https://nagios.example.com/nagios/cgi-bin',
            'admin', 'pass',
            'web01', 'HTTPS',
            1609459200, 1609545600)

        assert 'breakdown' in result
        assert 'log' in result
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        assert 'avail.cgi' in call_url
        assert 'host=web01' in call_url
        assert 'service=HTTPS' in call_url

    @patch('nagios.availability.requests.get')
    def test_fetch_uses_cache(self, mock_get, avail_html):
        from nagios.availability import fetch_availability, _cache
        _cache.clear()

        mock_resp = MagicMock()
        mock_resp.text = avail_html
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result1 = fetch_availability(
            'https://nagios.example.com/nagios/cgi-bin',
            'admin', 'pass',
            'web01', 'HTTPS',
            1609459200, 1609545600)
        result2 = fetch_availability(
            'https://nagios.example.com/nagios/cgi-bin',
            'admin', 'pass',
            'web01', 'HTTPS',
            1609459200, 1609545600)

        assert mock_get.call_count == 1
        assert result1 == result2


class TestCache:
    def test_cache_expires(self, avail_html):
        from nagios.availability import (
            _cache, _cache_put, _cache_get, _CACHE_LOCK
        )
        _cache.clear()

        key = ('url', 'host', 'svc', 100, 200)
        _cache_put(key, {'test': True})

        assert _cache_get(key) is not None

        with _CACHE_LOCK:
            _cache[key] = ({'test': True}, time.time() - 120)

        assert _cache_get(key) is None

    def test_cache_eviction(self):
        from nagios.availability import (
            _cache, _cache_put, _CACHE_MAX
        )
        _cache.clear()

        for i in range(_CACHE_MAX + 10):
            _cache_put(('url', 'host', 'svc', i, i + 1), {'i': i})

        assert len(_cache) <= _CACHE_MAX
