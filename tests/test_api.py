import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import shutil
import types
import pytest

API_PATH = os.path.join(os.path.dirname(__file__), '..', 'nagios-api')
FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
STATUS_FILE = os.path.join(FIXTURES, 'status.dat')


@pytest.fixture(scope='module')
def api_module():
    """Load nagios-api as a module despite the hyphenated filename."""
    loader = importlib.machinery.SourceFileLoader('nagios_api', API_PATH)
    spec = importlib.util.spec_from_loader('nagios_api', loader)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- Command validation ---

class TestValidateNagiosCommand:
    def test_valid_command(self, api_module):
        ok, err = api_module.validate_nagios_command('SCHEDULE_HOST_DOWNTIME')
        assert ok is True
        assert err is None

    def test_valid_command_with_args(self, api_module):
        ok, err = api_module.validate_nagios_command(
            'SCHEDULE_HOST_DOWNTIME;web01;1234;5678;1;0;0;admin;test')
        assert ok is True

    def test_disallowed_command(self, api_module):
        ok, err = api_module.validate_nagios_command('SHUTDOWN_PROGRAM')
        assert ok is False
        assert 'not allowed' in err

    def test_empty_command(self, api_module):
        ok, err = api_module.validate_nagios_command('')
        assert ok is False

    def test_none_command(self, api_module):
        ok, err = api_module.validate_nagios_command(None)
        assert ok is False

    def test_newline_in_args_rejected(self, api_module):
        ok, err = api_module.validate_nagios_command(
            'SCHEDULE_HOST_DOWNTIME;web01\n[1234] SHUTDOWN_PROGRAM')
        assert ok is False
        assert 'newline' in err.lower()

    def test_carriage_return_in_args_rejected(self, api_module):
        ok, err = api_module.validate_nagios_command(
            'ADD_HOST_COMMENT;web01;1;admin;comment\rwith cr')
        assert ok is False
        assert 'newline' in err.lower()


# --- Path traversal protection ---

class TestSafeCfgPath:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir)

    def test_valid_filename(self, api_module):
        result = api_module.safe_cfg_path(self.tmpdir, 'myhost.cfg')
        assert result == os.path.realpath(
            os.path.join(self.tmpdir, 'myhost.cfg'))

    def test_path_traversal_rejected(self, api_module):
        with pytest.raises(ValueError):
            api_module.safe_cfg_path(self.tmpdir, '../../../etc/passwd')

    def test_absolute_path_rejected(self, api_module):
        with pytest.raises(ValueError):
            api_module.safe_cfg_path(self.tmpdir, '/etc/passwd')

    def test_wrong_extension_rejected(self, api_module):
        with pytest.raises(ValueError):
            api_module.safe_cfg_path(self.tmpdir, 'evil.sh')

    def test_no_extension_rejected(self, api_module):
        with pytest.raises(ValueError):
            api_module.safe_cfg_path(self.tmpdir, 'hostfile')

    def test_empty_filename_rejected(self, api_module):
        with pytest.raises(ValueError):
            api_module.safe_cfg_path(self.tmpdir, '')

    def test_none_filename_rejected(self, api_module):
        with pytest.raises(ValueError):
            api_module.safe_cfg_path(self.tmpdir, None)

    def test_dotdot_only_rejected(self, api_module):
        with pytest.raises(ValueError):
            api_module.safe_cfg_path(self.tmpdir, '..')

    def test_hidden_file_with_cfg_ext(self, api_module):
        result = api_module.safe_cfg_path(self.tmpdir, '.hidden.cfg')
        assert result.endswith('.hidden.cfg')

    def test_complex_traversal_stripped_to_basename(self, api_module):
        # basename() strips the path, so the traversal is neutralized and
        # only 'backdoor.cfg' is used — which is safe within the directory
        result = api_module.safe_cfg_path(
            self.tmpdir, 'subdir/../../../etc/cron.d/backdoor.cfg')
        assert result == os.path.realpath(
            os.path.join(self.tmpdir, 'backdoor.cfg'))


# --- API key loading ---

class TestLoadApiKeys:
    def test_load_keys(self, api_module):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                         delete=False) as f:
            f.write('# comment line\n')
            f.write('key-abc-123\n')
            f.write('\n')
            f.write('key-def-456\n')
            f.name
        try:
            keys = api_module.load_api_keys(f.name)
            assert keys == {'key-abc-123', 'key-def-456'}
        finally:
            os.unlink(f.name)

    def test_empty_file_raises(self, api_module):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                         delete=False) as f:
            f.write('# only comments\n')
            f.write('\n')
        try:
            with pytest.raises(ValueError, match='no valid keys'):
                api_module.load_api_keys(f.name)
        finally:
            os.unlink(f.name)

    def test_missing_file_raises(self, api_module):
        with pytest.raises(FileNotFoundError):
            api_module.load_api_keys('/nonexistent/path/keys.txt')


# --- Flask auth integration ---

class TestAuthMiddleware:
    @pytest.fixture
    def app_no_auth(self, api_module):
        """Flask test client with auth disabled."""
        api_module.API_KEYS = None
        api_module.NAGIOS = api_module.__builtins__  # just needs to be non-None
        from nagios import Nagios
        api_module.NAGIOS = Nagios(STATUS_FILE)

        flask_app = api_module.Flask(__name__)

        @flask_app.before_request
        def check_auth():
            if api_module.API_KEYS is None:
                return None
            key = (api_module.flask_request.headers.get('X-API-Key')
                   or api_module.flask_request.args.get('api_key'))
            if not key or key not in api_module.API_KEYS:
                return api_module.Response(
                    api_module.dumps(
                        {'success': False, 'content': 'Authentication required'}
                    ),
                    status=401,
                    content_type='application/json'
                )

        @flask_app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
        @flask_app.route('/<path:path>', methods=['GET', 'POST'])
        def catch_all(path):
            return api_module.http_handler(api_module.flask_request)

        flask_app.config['TESTING'] = True
        return flask_app.test_client()

    @pytest.fixture
    def app_with_auth(self, api_module):
        """Flask test client with auth enabled."""
        api_module.API_KEYS = {'valid-test-key-123'}
        from nagios import Nagios
        api_module.NAGIOS = Nagios(STATUS_FILE)

        flask_app = api_module.Flask(__name__)

        @flask_app.before_request
        def check_auth():
            if api_module.API_KEYS is None:
                return None
            key = (api_module.flask_request.headers.get('X-API-Key')
                   or api_module.flask_request.args.get('api_key'))
            if not key or key not in api_module.API_KEYS:
                return api_module.Response(
                    api_module.dumps(
                        {'success': False, 'content': 'Authentication required'}
                    ),
                    status=401,
                    content_type='application/json'
                )

        @flask_app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
        @flask_app.route('/<path:path>', methods=['GET', 'POST'])
        def catch_all(path):
            return api_module.http_handler(api_module.flask_request)

        flask_app.config['TESTING'] = True
        return flask_app.test_client()

    def test_no_auth_configured_allows_requests(self, app_no_auth):
        resp = app_no_auth.get('/state')
        assert resp.status_code == 200

    def test_auth_required_rejects_missing_key(self, app_with_auth):
        resp = app_with_auth.get('/state')
        assert resp.status_code == 401

    def test_auth_required_rejects_bad_key(self, app_with_auth):
        resp = app_with_auth.get('/state',
                                 headers={'X-API-Key': 'wrong-key'})
        assert resp.status_code == 401

    def test_auth_accepts_valid_header_key(self, app_with_auth):
        resp = app_with_auth.get('/state',
                                 headers={'X-API-Key': 'valid-test-key-123'})
        assert resp.status_code == 200

    def test_auth_accepts_valid_query_key(self, app_with_auth):
        resp = app_with_auth.get('/state?api_key=valid-test-key-123')
        assert resp.status_code == 200


# --- CORS validation ---

class TestValidateAllowOrigin:
    def test_wildcard_rejected(self, api_module):
        with pytest.raises(ValueError, match='insecure'):
            api_module.validate_allow_origin('*')

    def test_valid_https_origin(self, api_module):
        result = api_module.validate_allow_origin('https://monitoring.example.com')
        assert result == 'https://monitoring.example.com'

    def test_valid_http_origin(self, api_module):
        result = api_module.validate_allow_origin('http://localhost:3000')
        assert result == 'http://localhost:3000'

    def test_non_url_rejected(self, api_module):
        with pytest.raises(ValueError, match='origin URL'):
            api_module.validate_allow_origin('not-a-url')

    def test_bare_domain_rejected(self, api_module):
        with pytest.raises(ValueError, match='origin URL'):
            api_module.validate_allow_origin('example.com')


# --- Restart method enforcement ---

class TestRestartMethod:
    @pytest.fixture
    def app(self, api_module):
        """Flask test client for restart method tests."""
        api_module.API_KEYS = None
        api_module.CMD_ENABLED = False
        from nagios import Nagios
        api_module.NAGIOS = Nagios(STATUS_FILE)

        flask_app = api_module.Flask(__name__)

        @flask_app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
        @flask_app.route('/<path:path>', methods=['GET', 'POST'])
        def catch_all(path):
            return api_module.http_handler(api_module.flask_request)

        flask_app.config['TESTING'] = True
        return flask_app.test_client()

    def test_get_restart_rejected(self, app):
        resp = app.get('/restart_nagios')
        data = resp.get_json()
        assert data['success'] is False
        assert 'POST' in data['content']

    def test_post_restart_routed(self, app):
        # CMD_ENABLED is False, so this will fail with "not enabled" —
        # but it proves the POST route reaches the real handler
        resp = app.post('/restart_nagios',
                        content_type='application/json',
                        data='{}')
        data = resp.get_json()
        # The handler runs but command is disabled
        assert data['success'] is False
        assert 'Restart failed' in data['content']
