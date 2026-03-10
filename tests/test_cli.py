import importlib.machinery
import importlib.util
import os
import sys
import types
import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), '..', 'nagios-cli')


@pytest.fixture(scope='module')
def cli_module():
    """Load nagios-cli as a module despite the hyphenated filename."""
    # Ensure 'requests' is importable (stub it if missing so pure utility
    # functions can still be tested).
    if 'requests' not in sys.modules:
        try:
            import requests  # noqa: F401
        except ImportError:
            sys.modules['requests'] = types.ModuleType('requests')

    loader = importlib.machinery.SourceFileLoader('nagios_cli', CLI_PATH)
    spec = importlib.util.spec_from_loader('nagios_cli', loader)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTimeToSeconds:
    def test_plain_seconds(self, cli_module):
        assert cli_module.time_to_seconds('300') == 300

    def test_seconds_suffix(self, cli_module):
        assert cli_module.time_to_seconds('30s') == 30

    def test_minutes(self, cli_module):
        assert cli_module.time_to_seconds('5m') == 300

    def test_hours(self, cli_module):
        assert cli_module.time_to_seconds('2h') == 7200

    def test_days(self, cli_module):
        assert cli_module.time_to_seconds('1d') == 86400

    def test_weeks(self, cli_module):
        assert cli_module.time_to_seconds('1w') == 604800

    def test_invalid_returns_none(self, cli_module):
        assert cli_module.time_to_seconds('abc') is None

    def test_empty_returns_none(self, cli_module):
        assert cli_module.time_to_seconds('') is None

    def test_zero(self, cli_module):
        assert cli_module.time_to_seconds('0') == 0

    def test_zero_hours(self, cli_module):
        assert cli_module.time_to_seconds('0h') == 0


class TestTrim:
    def test_trims_docstring(self, cli_module):
        result = cli_module.trim("""
            First line.
            Second line.
        """)
        assert result == 'First line.\nSecond line.'

    def test_empty_string(self, cli_module):
        assert cli_module.trim('') == ''

    def test_none(self, cli_module):
        assert cli_module.trim(None) == ''
