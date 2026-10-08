import io
import logging
import unittest

from app.log_privacy import install_private_logging


class LogPrivacyTests(unittest.TestCase):
    def setUp(self):
        install_private_logging()
        self.output = io.StringIO()
        self.handler = logging.StreamHandler(self.output)
        self.logger = logging.getLogger('privacy-test')
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)

    def tearDown(self):
        self.logger.removeHandler(self.handler)

    def test_payloads_queries_and_exceptions_are_not_formatted(self):
        secret = 'PRIVATE-CANARY-token-and-memory'
        self.logger.info('LLM reply: %s', secret)
        self.logger.info(f'https://provider.example/?token={secret}')
        self.logger.warning('failure %s', ValueError(secret))
        try:
            raise ValueError(secret)
        except ValueError:
            self.logger.exception('payload=%s', secret, stack_info=True)
        rendered = self.output.getvalue()
        self.assertNotIn(secret, rendered)
        self.assertNotIn('provider.example', rendered)
        self.assertIn('ValueError', rendered)

    def test_access_formatter_receives_redacted_five_tuple(self):
        record = logging.getLogger('uvicorn.access').makeRecord('uvicorn.access', 20, __file__, 1,
            '%s - "%s %s HTTP/%s" %d', ('private-ip', 'GET', '/?token=CANARY', '1.1', 401), None)
        from uvicorn.logging import AccessFormatter
        rendered = AccessFormatter('%(message)s').format(record)
        self.assertNotIn('CANARY', rendered)
        self.assertNotIn('private-ip', rendered)
        self.assertIn('401', rendered)

    def test_audit_keeps_safe_fields(self):
        record = logging.getLogger('remoire.http').makeRecord('remoire.http', 20, __file__, 1,
            'request_id=%s method=%s route=%s status=%s duration_ms=%.2f',
            ('12345678-1234-1234-1234-123456789abc', 'POST', '/api/memory/{memory_id}', 401, 1.25), None)
        self.assertIn('status=401', record.getMessage())
        self.assertIn('/api/memory/{memory_id}', record.getMessage())
