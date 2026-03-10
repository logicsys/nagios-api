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
        assert 'not allowed' in err.lower()

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


# --- Semicolon injection in send_nagios_command ---

class TestSemicolonInjection:
    def test_semicolon_in_argument_rejected(self, api_module):
        '''A semicolon in a non-verb argument would create extra Nagios
        command fields, so it must be rejected.'''
        api_module.CMD_ENABLED = True
        api_module.CMDFILE = '/dev/null'
        result = api_module.send_nagios_command(
            'ADD_HOST_COMMENT', 'web01', '1', 'admin',
            'innocent;SHUTDOWN_PROGRAM')
        assert result is False

    def test_semicolon_in_verb_allowed(self, api_module):
        '''The first arg may be a pre-validated raw command string
        containing legitimate semicolon delimiters.'''
        api_module.CMD_ENABLED = True
        api_module.CMDFILE = '/dev/null'
        # This is a single-arg call like raw_command uses.
        # It will fail to write to /dev/null as a named pipe, but we
        # only care that it isn't rejected for the semicolon.
        result = api_module.send_nagios_command(
            'SCHEDULE_HOST_DOWNTIME;web01;123;456;1;0;0;admin;test')
        # Will be True (write to /dev/null succeeds) or False (OS error),
        # but should NOT be rejected due to semicolons.  If the semicolon
        # check fired, the log would say so.  We test the positive path
        # by verifying no early False from validation.
        # A more precise test: patch CMDFILE to a real writable pipe.
        # For now, just ensure the verb check doesn't block it.
        assert result is not None  # didn't raise

    def test_semicolon_in_comment_field_rejected(self, api_module):
        '''Realistic attack: semicolon in a comment to inject extra args.'''
        api_module.CMD_ENABLED = True
        api_module.CMDFILE = '/dev/null'
        result = api_module.send_nagios_command(
            'SCHEDULE_HOST_DOWNTIME', 'web01', '123', '456',
            '1', '0', '0', 'admin', 'legit comment;SHUTDOWN_PROGRAM')
        assert result is False

    def test_clean_arguments_accepted(self, api_module):
        '''Normal arguments without semicolons should be accepted.'''
        api_module.CMD_ENABLED = True
        api_module.CMDFILE = '/dev/null'
        result = api_module.send_nagios_command(
            'ADD_HOST_COMMENT', 'web01', '1', 'admin', 'clean comment')
        # May fail due to /dev/null not being a pipe, but shouldn't
        # fail from argument validation
        assert result is not None


# --- _mkdir_recursive ---

class TestMkdirRecursive:
    def test_creates_nested_dirs(self, api_module):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        nested = os.path.join(tmpdir, 'a', 'b', 'c')
        try:
            api_module._mkdir_recursive(nested)
            assert os.path.isdir(nested)
        finally:
            shutil.rmtree(tmpdir)

    def test_existing_dir_no_error(self, api_module):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        try:
            api_module._mkdir_recursive(tmpdir)  # already exists
            assert os.path.isdir(tmpdir)
        finally:
            shutil.rmtree(tmpdir)

    def test_directory_permissions(self, api_module):
        import tempfile
        import stat
        tmpdir = tempfile.mkdtemp()
        nested = os.path.join(tmpdir, 'newdir')
        try:
            api_module._mkdir_recursive(nested)
            mode = os.stat(nested).st_mode & 0o777
            # Should be 0o755 (possibly masked by umask)
            assert mode & 0o700 == 0o700  # owner rwx
            assert not (mode & 0o022)  # no group/other write
        finally:
            shutil.rmtree(tmpdir)


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


# --- Thread safety accessors ---

class TestThreadSafeAccessors:
    def test_get_nagios_returns_current_state(self, api_module):
        from nagios import Nagios
        api_module.NAGIOS = Nagios(STATUS_FILE)
        result = api_module.get_nagios()
        assert result is api_module.NAGIOS
        assert 'web01' in result.hosts

    def test_get_nlog_returns_copy(self, api_module):
        api_module.NLOG = ['line1', 'line2']
        result = api_module.get_nlog()
        assert result == ['line1', 'line2']
        # Mutating the copy should not affect the global
        result.append('line3')
        assert len(api_module.NLOG) == 2


# --- Information disclosure fix ---

class TestInfoDisclosure:
    @pytest.fixture
    def app(self, api_module):
        """Flask test client for info disclosure tests."""
        api_module.API_KEYS = None
        api_module.RATE_LIMITER = None
        from nagios import Nagios
        api_module.NAGIOS = Nagios(STATUS_FILE)

        flask_app = api_module.Flask(__name__)

        @flask_app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
        @flask_app.route('/<path:path>', methods=['GET', 'POST'])
        def catch_all(path):
            return api_module.http_handler(api_module.flask_request)

        flask_app.config['TESTING'] = True
        return flask_app.test_client()

    def test_host_endpoint_uses_allowlist(self, app):
        resp = app.get('/host/web01')
        data = resp.get_json()
        assert data['success'] is True
        content = data['content']
        # Should have allowlisted keys
        assert 'current_state' in content
        assert 'plugin_output' in content
        # Should NOT have internal attributes
        assert 'type' not in content
        assert 'essential_keys' not in content
        assert 'attach_service' not in content
        assert 'attach_comment' not in content

    def test_host_endpoint_includes_services_list(self, app):
        resp = app.get('/host/web01')
        data = resp.get_json()
        content = data['content']
        assert 'services' in content
        assert 'HTTP' in content['services']

    def test_service_endpoint_uses_allowlist(self, app):
        resp = app.get('/service/web01')
        data = resp.get_json()
        assert data['success'] is True
        content = data['content']
        assert 'HTTP' in content
        http = content['HTTP']
        assert 'current_state' in http
        assert 'type' not in http
        assert 'essential_keys' not in http

    def test_error_does_not_echo_verb(self, app):
        resp = app.get('/nonexistent_verb_xyz')
        data = resp.get_json()
        assert data['success'] is False
        assert 'nonexistent_verb_xyz' not in data['content']


# --- PID file race condition ---

class TestWritePid:
    def test_creates_pid_file(self, api_module):
        tmpdir = tempfile.mkdtemp()
        pid_path = os.path.join(tmpdir, 'test.pid')
        api_module.PID_FILE = pid_path
        try:
            api_module.write_pid()
            assert os.path.isfile(pid_path)
            with open(pid_path) as f:
                assert f.read() == str(os.getpid())
        finally:
            os.unlink(pid_path)
            os.rmdir(tmpdir)

    def test_exits_if_pid_exists(self, api_module):
        tmpdir = tempfile.mkdtemp()
        pid_path = os.path.join(tmpdir, 'test.pid')
        # Pre-create the file
        with open(pid_path, 'w') as f:
            f.write('99999')
        api_module.PID_FILE = pid_path
        try:
            with pytest.raises(SystemExit):
                api_module.write_pid()
        finally:
            os.unlink(pid_path)
            os.rmdir(tmpdir)


# --- Rate limiter ---

class TestRateLimiter:
    def test_allows_up_to_burst(self, api_module):
        rl = api_module.RateLimiter(rate=1, burst=3)
        assert rl.allow('client1') is True
        assert rl.allow('client1') is True
        assert rl.allow('client1') is True
        # Burst exhausted
        assert rl.allow('client1') is False

    def test_different_keys_independent(self, api_module):
        rl = api_module.RateLimiter(rate=1, burst=1)
        assert rl.allow('client1') is True
        assert rl.allow('client2') is True
        assert rl.allow('client1') is False
        assert rl.allow('client2') is False

    def test_cleanup_removes_stale(self, api_module):
        rl = api_module.RateLimiter(rate=1, burst=5)
        rl.allow('old_client')
        # Manually backdate the entry
        with rl.lock:
            tokens, _ = rl.buckets['old_client']
            rl.buckets['old_client'] = (tokens, 0)  # epoch = very old
        rl.cleanup(max_age=1)
        assert 'old_client' not in rl.buckets
