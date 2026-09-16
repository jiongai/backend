"""Security regression tests for authentication, logs, and error responses."""

import asyncio
import json
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from app.core.logging import control_exception_details, redact_sensitive_data
from app.main import unhandled_exception_handler, verify_secret_key


class AuthenticationTests(unittest.TestCase):
    def test_production_fails_closed_when_secret_is_missing(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(verify_secret_key(None))

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail["code"],
            "authentication_not_configured",
        )

    def test_development_can_explicitly_run_without_authentication(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            result = asyncio.run(verify_secret_key(None))

        self.assertIsNone(result)

    def test_missing_invalid_and_valid_secrets_are_distinguished(self):
        environment = {
            "ENVIRONMENT": "production",
            "DARMAFLOW_API_ACCESS_SECRET": "server-secret",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(HTTPException) as missing:
                asyncio.run(verify_secret_key(None))
            with self.assertRaises(HTTPException) as invalid:
                asyncio.run(verify_secret_key("wrong-secret"))
            valid_result = asyncio.run(verify_secret_key("server-secret"))

        self.assertEqual(missing.exception.status_code, 401)
        self.assertEqual(invalid.exception.status_code, 403)
        self.assertIsNone(valid_result)


class LoggingAndErrorResponseTests(unittest.TestCase):
    def test_production_logs_drop_stacktraces_by_default(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            event = control_exception_details(
                None,
                None,
                {"event": "failed", "exc_info": True, "stack": "sensitive"},
            )

        self.assertNotIn("exc_info", event)
        self.assertNotIn("stack", event)

    def test_log_processor_redacts_keys_nested_values_and_known_secrets(self):
        secret = "super-sensitive-value"
        with patch.dict(
            os.environ,
            {"R2_SECRET_ACCESS_KEY": secret},
            clear=True,
        ):
            sanitized = redact_sensitive_data(
                None,
                None,
                {
                    "api_key": "key-value",
                    "nested": {"authorization": "Bearer token"},
                    "event": f"provider failed with {secret}",
                },
            )

        serialized = repr(sanitized)
        self.assertNotIn("key-value", serialized)
        self.assertNotIn("Bearer token", serialized)
        self.assertNotIn(secret, serialized)
        self.assertIn("[REDACTED]", serialized)

    def test_unhandled_error_response_does_not_expose_exception_details(self):
        request = Request({
            "type": "http",
            "method": "GET",
            "path": "/explode",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        })
        sensitive_detail = "/private/tmp/internal-secret.txt"

        try:
            raise RuntimeError(sensitive_detail)
        except RuntimeError as exc:
            response = asyncio.run(unhandled_exception_handler(request, exc))

        body = json.loads(response.body)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(body["detail"]["code"], "internal_server_error")
        self.assertNotIn(sensitive_detail, response.body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
