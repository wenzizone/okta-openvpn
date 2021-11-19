import os
import tempfile

from mock import MagicMock
from mock import patch

from okta_openvpn import OktaOpenVPNValidator
from tests.shared import MockEnviron
from tests.shared import OktaTestCase
from tests.shared import ThrowsErrorOktaAPI
import okta_openvpn


class TestOktaAPIAuth(OktaTestCase):
    def setUp(self):
        super(TestOktaAPIAuth, self).setUp()
        self.config['assert_pinset'] = [self.herokuapp_dot_com_pin]

    def test_invalid_configuration_file(self):
        validator = OktaOpenVPNValidator()
        validator.config_file = '/dev/false'
        rv = validator.read_configuration_file()
        self.assertEquals(rv, False)
        last_error = self.okta_log_messages['critical'][-1:][0]
        self.assertIn('Failed to load config', last_error)

    def test_no_okta_url(self):
        env = MockEnviron({})
        validator = OktaOpenVPNValidator()
        validator.env = env
        rv = validator.load_environment_variables()
        self.assertEquals(rv, False)
        last_error = self.okta_log_messages['critical'][-1:][0]
        self.assertIn('OKTA_URL not defined', last_error)

    def test_okta_url_no_token(self):
        cfg = {
            'okta_url': self.okta_url
        }
        # Empty out the Mock Environment
        env = MockEnviron({})
        validator = OktaOpenVPNValidator()
        validator.site_config = cfg
        validator.env = env
        rv = validator.load_environment_variables()
        self.assertEquals(rv, False)
        last_error = self.okta_log_messages['critical'][-1:][0]
        self.assertIn('OKTA_TOKEN not defined', last_error)

    def test_no_username_or_password(self):
        # Make our own config with out username or password
        cfg = {
            'okta_url': self.okta_url,
            'okta_token': self.okta_token,
            }
        env = MockEnviron({})
        validator = OktaOpenVPNValidator()
        validator.site_config = cfg
        validator.env = env
        rv = validator.load_environment_variables()
        rv = validator.authenticate()
        self.assertEquals(rv, False)
        last_error = self.okta_log_messages['warning'][-1:][0]
        self.assertIn('is not trusted - failing', last_error)

    def test_okta_verify_push(self):
        cfg = {
            'okta_url': self.okta_url,
            'okta_token': self.okta_token,
            'mfa_push_max_retries': 20,
            'mfa_push_delay_secs': self.mfa_push_delay_secs,
            }
        env = MockEnviron({
            'common_name': 'user_MFA_PUSH@example.com',
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.site_config = cfg
        validator.env = env
        validator.load_environment_variables()
        validator.okta_config['assert_pinset'] = [self.herokuapp_dot_com_pin]

        rv = validator.authenticate()
        self.assertEquals(rv, True)
        last_error = self.okta_log_messages['info'][-1]
        self.assertIn('is now authenticated with MFA via Okta API', last_error)

    @patch('time.sleep', return_value=None)
    def test_okta_verify_push_int(self, patched_time_sleep):
        cfg = {
            'okta_url': self.okta_url,
            'okta_token': self.okta_token,
            'mfa_push_max_retries': int(20),
            'mfa_push_delay_secs': int(11),
            }
        env = MockEnviron({
            'common_name': 'user_MFA_PUSH@example.com',
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.site_config = cfg
        validator.env = env
        validator.load_environment_variables()
        validator.okta_config['assert_pinset'] = [self.herokuapp_dot_com_pin]
        validator.authenticate()
        for call in patched_time_sleep.call_args_list:
            args, kwargs = call
            for arg in args:
                import pprint
                pprint.pprint(arg)
                msg = "time.sleep() must be called with a float not %s"
                assert isinstance(arg, float), msg % type(arg)
        patched_time_sleep.assert_called_with(11)

    def test_okta_verify_push_timeout(self):
        cfg = {
            'okta_url': self.okta_url,
            'okta_token': self.okta_token,
            'mfa_push_max_retries': 1,
            'mfa_push_delay_secs': self.mfa_push_delay_secs,
            }
        env = MockEnviron({
            'common_name': 'user_MFA_PUSH@example.com',
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.site_config = cfg
        validator.env = env
        validator.load_environment_variables()
        validator.okta_config['assert_pinset'] = [self.herokuapp_dot_com_pin]

        rv = validator.authenticate()
        self.assertEquals(rv, False)
        last_error = self.okta_log_messages['info'][-1]
        self.assertIn('push timed out', last_error)

    def test_okta_verify_push_fails(self):
        cfg = {
            'okta_url': self.okta_url,
            'okta_token': self.okta_token,
            'mfa_push_max_retries': 20,
            'mfa_push_delay_secs': self.mfa_push_delay_secs,
            }
        env = MockEnviron({
            'common_name': 'user_MFA_PUSH_REJECTED@example.com',
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.site_config = cfg
        validator.env = env
        validator.load_environment_variables()
        validator.okta_config['assert_pinset'] = [self.herokuapp_dot_com_pin]

        rv = validator.authenticate()
        self.assertEquals(rv, False)

    def test_with_username_and_password(self):
        cfg = {
            'okta_url': self.okta_url,
            'okta_token': self.okta_token,
            }
        env = MockEnviron({
            'common_name': self.config['username'],
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.site_config = cfg
        validator.env = env
        validator.load_environment_variables()
        validator.okta_config['assert_pinset'] = [self.herokuapp_dot_com_pin]

        rv = validator.authenticate()
        self.assertEquals(rv, True)
        last_error = self.okta_log_messages['info'][-1:][0]
        self.assertIn('is now authenticated with MFA via Okta API', last_error)

    def test_with_valid_config_file(self):
        config_format = (
            "[OktaAPI]\n"
            "Url: {}\n"
            "Token: {}\n")
        cfg = tempfile.NamedTemporaryFile()
        cfg.file.write(config_format.format(
            self.okta_url,
            self.okta_token).encode())
        cfg.file.seek(0)
        env = MockEnviron({
            'common_name': self.config['username'],
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.config_file = cfg.name
        validator.env = env
        validator.read_configuration_file()
        validator.load_environment_variables()
        # Disable Public Key Pinning
        validator.okta_config['assert_pinset'] = [self.herokuapp_dot_com_pin]
        rv = validator.authenticate()
        self.assertEquals(rv, True)
        last_error = self.okta_log_messages['info'][-1:][0]
        self.assertIn('is now authenticated with MFA via Okta API', last_error)

    def test_with_valid_config_file_with_untrusted_user_enabled(self):
        config_format = (
            "[OktaAPI]\n"
            "Url: {}\n"
            "Token: {}\n"
            "AllowUntrustedUsers: True")
        cfg = tempfile.NamedTemporaryFile()
        cfg.file.write(config_format.format(
            self.okta_url,
            self.okta_token).encode())
        cfg.file.seek(0)
        env = MockEnviron({
            'username': self.config['username'],
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.config_file = cfg.name
        validator.env = env
        validator.read_configuration_file()
        validator.load_environment_variables()
        # Disable Public Key Pinning
        validator.okta_config['assert_pinset'] = [self.herokuapp_dot_com_pin]
        rv = validator.authenticate()
        self.assertEquals(rv, True)
        last_error = self.okta_log_messages['info'][-1:][0]
        self.assertIn('is now authenticated with MFA via Okta API', last_error)

    def test_with_valid_config_file_with_untrusted_user_disabled(self):
        for val in ['yes', '1', 'true', 'ok', 'False', '0']:
            config_format = (
                "[OktaAPI]\n"
                "Url: {}\n"
                "Token: {}\n"
                "AllowUntrustedUsers: {}")
            cfg = tempfile.NamedTemporaryFile()
            cfg.file.write(config_format.format(
                self.okta_url,
                self.okta_token,
                val).encode())
            cfg.file.seek(0)
            env = MockEnviron({
                'username': self.config['username'],
                'password': self.config['password']
                })
            validator = OktaOpenVPNValidator()
            validator.config_file = cfg.name
            validator.env = env
            validator.read_configuration_file()
            validator.load_environment_variables()
            # Disable Public Key Pinning
            validator.okta_config['assert_pinset'] = [
                self.herokuapp_dot_com_pin]
            rv = validator.authenticate()
            self.assertEquals(rv, False)

    def test_suffix_with_username_and_password(self):
        cfg = {
            'okta_url': self.okta_url,
            'okta_token': self.okta_token,
            }
        env = MockEnviron({
            'common_name': self.username_prefix,
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.site_config = cfg
        validator.username_suffix = self.username_suffix
        validator.env = env
        validator.load_environment_variables()
        validator.okta_config['assert_pinset'] = [self.herokuapp_dot_com_pin]

        rv = validator.authenticate()
        self.assertEquals(rv, True)
        last_error = self.okta_log_messages['info'][-1:][0]
        self.assertIn('is now authenticated with MFA via Okta API', last_error)

    def test_suffix_where_username_contains_suffix_already(self):
        cfg = {
            'okta_url': self.okta_url,
            'okta_token': self.okta_token,
            }
        env = MockEnviron({
            'common_name': self.config['username'],
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.site_config = cfg
        validator.username_suffix = self.username_suffix
        validator.env = env
        validator.load_environment_variables()
        validator.okta_config['assert_pinset'] = [self.herokuapp_dot_com_pin]

        rv = validator.authenticate()
        self.assertEquals(rv, True)
        last_error = self.okta_log_messages['info'][-1:][0]
        self.assertIn('is now authenticated with MFA via Okta API', last_error)

    def test_suffix_with_valid_config_file(self):
        config_format = (
            "[OktaAPI]\n"
            "Url: {}\n"
            "Token: {}\n"
            "UsernameSuffix: {}\n")
        cfg = tempfile.NamedTemporaryFile()
        cfg.file.write(config_format.format(
            self.okta_url,
            self.okta_token,
            self.username_suffix).encode())
        cfg.file.seek(0)
        env = MockEnviron({
            'common_name': self.username_prefix,
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.config_file = cfg.name
        validator.env = env
        validator.read_configuration_file()
        validator.load_environment_variables()
        # Disable Public Key Pinning
        validator.okta_config['assert_pinset'] = [self.herokuapp_dot_com_pin]
        rv = validator.authenticate()
        self.assertEquals(rv, True)
        last_error = self.okta_log_messages['info'][-1:][0]
        self.assertIn('is now authenticated with MFA via Okta API', last_error)

    def test_with_invalid_config_file(self):
        cfg = tempfile.NamedTemporaryFile()
        cfg.file.write('invalidconfig'.encode())
        cfg.file.seek(0)
        env = MockEnviron({
            'common_name': self.config['username'],
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.config_file = cfg.name
        validator.env = env
        rv = validator.read_configuration_file()
        self.assertEquals(rv, False)

    def test_return_error_code_true(self):
        validator = OktaOpenVPNValidator()
        validator.user_valid = True
        okta_openvpn.sys = MagicMock()
        okta_openvpn.return_error_code_for(validator)
        okta_openvpn.sys.exit.assert_called_with(0)

    def test_return_error_code_false(self):
        validator = OktaOpenVPNValidator()
        validator.user_valid = False
        okta_openvpn.sys = MagicMock()
        okta_openvpn.return_error_code_for(validator)
        okta_openvpn.sys.exit.assert_called_with(1)

    def test_authenticate_handles_exceptions(self):
        cfg = {
            'okta_url': self.okta_url,
            'okta_token': self.okta_token,
            }
        env = MockEnviron({
            'common_name': self.config['username'],
            'password': self.config['password']
            })
        validator = OktaOpenVPNValidator()
        validator.cls = ThrowsErrorOktaAPI
        validator.site_config = cfg
        validator.env = env
        validator.load_environment_variables()
        rv = validator.authenticate()
        self.assertEquals(rv, False)
        last_error = self.okta_log_messages['error'][-1:][0]
        self.assertIn('authentication failed, because', last_error)

    def test_write_0_to_control_file(self):
        tmp = tempfile.NamedTemporaryFile()
        validator = OktaOpenVPNValidator()
        validator.control_file = tmp.name
        validator.write_result_to_control_file()
        tmp.file.seek(0)
        rv = tmp.file.read()
        self.assertEquals(rv, '0')

    def test_write_1_to_control_file(self):
        tmp = tempfile.NamedTemporaryFile()
        validator = OktaOpenVPNValidator()
        validator.user_valid = True
        validator.control_file = tmp.name
        validator.write_result_to_control_file()
        tmp.file.seek(0)
        rv = tmp.file.read()
        self.assertEquals(rv, '1')

    def test_write_ro_to_control_file(self):
        tmp = tempfile.NamedTemporaryFile()
        os.chmod(tmp.name, 0o400)
        validator = OktaOpenVPNValidator()
        validator.user_valid = True
        validator.control_file = tmp.name
        validator.write_result_to_control_file()
        tmp.file.seek(0)
        rv = tmp.file.read()
        self.assertEquals(rv, '')

        tmp.file.seek(0)
        validator.user_valid = False
        validator.write_result_to_control_file()
        tmp.file.seek(0)
        rv = tmp.file.read()
        self.assertEquals(rv, '')

    def test_OktaOpenVPNValidator_run(self):
        cfg = {
            'okta_url': self.okta_url,
            'okta_token': self.okta_token,
            }
        tmp = tempfile.NamedTemporaryFile()
        env = MockEnviron({
            'common_name': self.config['username'],
            'password': self.config['password'],
            'auth_control_file': tmp.name,
            'assert_pin': self.herokuapp_dot_com_pin,
            })

        validator = OktaOpenVPNValidator()
        validator.site_config = cfg
        validator.env = env

        validator.run()

        self.assertTrue(validator.user_valid)
        tmp.file.seek(0)
        rv = tmp.file.read()
        self.assertEquals(rv, '1')
        last_error = self.okta_log_messages['info'][-1:][0]
        self.assertIn('is now authenticated with MFA via Okta API', last_error)

    # def test_control_file_world_writeable
    # def test_control_file_ro_gives_error
    # def test_tmp_dir_bad_permissions
