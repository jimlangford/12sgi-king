import json
import tempfile
import unittest
from pathlib import Path

from tools.auth.import_google_credentials import DEFAULT_CALLBACK, import_credentials
from tools.auth.import_smtp_credentials import import_smtp_credentials


class TestGoogleCredentialsImport(unittest.TestCase):
    def test_imports_web_client_without_disturbing_other_env_values(self):
        with tempfile.TemporaryDirectory(prefix="google-auth-import-") as tmp:
            root = Path(tmp)
            credentials = root / "credentials.json"
            env_file = root / ".env.v2"
            credentials.write_text(
                json.dumps(
                    {
                        "web": {
                            "client_id": "client-id.apps.googleusercontent.com",
                            "client_secret": "client-secret",
                            "redirect_uris": [DEFAULT_CALLBACK],
                            "javascript_origins": [
                                "https://elementlotus.com",
                                "https://elementlotus.com/",
                                "javascript:alert(1)",
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )
            env_file.write_text(
                "AUTH_SIGNING_SECRET=keep-me\n"
                "GOOGLE_CLIENT_ID=\n"
                "GOOGLE_CLIENT_SECRET=\n"
                "CORS_ORIGINS=https://12sgi.com\n",
                encoding="utf-8",
            )

            callback_registered = import_credentials(credentials, env_file, DEFAULT_CALLBACK)

            self.assertTrue(callback_registered)
            text = env_file.read_text(encoding="utf-8")
            self.assertIn("AUTH_SIGNING_SECRET=keep-me", text)
            self.assertIn("GOOGLE_CLIENT_ID=client-id.apps.googleusercontent.com", text)
            self.assertIn("GOOGLE_CLIENT_SECRET=client-secret", text)
            self.assertIn(
                "CORS_ORIGINS=https://12sgi.com,https://elementlotus.com",
                text,
            )
            self.assertNotIn("javascript:alert", text)

    def test_rejects_installed_application_credentials(self):
        with tempfile.TemporaryDirectory(prefix="google-auth-import-") as tmp:
            root = Path(tmp)
            credentials = root / "credentials.json"
            credentials.write_text(
                json.dumps({"installed": {"client_id": "id", "client_secret": "secret"}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "web application"):
                import_credentials(credentials, root / ".env.v2", DEFAULT_CALLBACK)

    def test_rejects_multiline_values_instead_of_injecting_env_entries(self):
        with tempfile.TemporaryDirectory(prefix="google-auth-import-") as tmp:
            root = Path(tmp)
            credentials = root / "credentials.json"
            credentials.write_text(
                json.dumps(
                    {
                        "web": {
                            "client_id": "client-id\nINJECTED=true",
                            "client_secret": "client-secret",
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "line breaks"):
                import_credentials(credentials, root / ".env.v2", DEFAULT_CALLBACK)


class TestSmtpCredentialsImport(unittest.TestCase):
    def test_imports_existing_mailroom_sender(self):
        with tempfile.TemporaryDirectory(prefix="smtp-auth-import-") as tmp:
            root = Path(tmp)
            credentials = root / "mail.json"
            env_file = root / ".env.v2"
            credentials.write_text(
                json.dumps(
                    {
                        "host": "smtp.gmail.com",
                        "port": 587,
                        "user": "owner@example.com",
                        "password": "app-password",
                        "from": "owner@example.com",
                    }
                ),
                encoding="utf-8",
            )
            env_file.write_text("AUTH_SIGNING_SECRET=keep-me\n", encoding="utf-8")

            import_smtp_credentials(credentials, env_file)

            text = env_file.read_text(encoding="utf-8")
            self.assertIn("AUTH_SIGNING_SECRET=keep-me", text)
            self.assertIn("SMTP_HOST=smtp.gmail.com", text)
            self.assertIn("SMTP_PORT=587", text)
            self.assertIn("SMTP_USER=owner@example.com", text)
            self.assertIn("SMTP_PASS=app-password", text)
            self.assertIn("SMTP_STARTTLS=true", text)

    def test_rejects_placeholder_password(self):
        with tempfile.TemporaryDirectory(prefix="smtp-auth-import-") as tmp:
            root = Path(tmp)
            credentials = root / "mail.json"
            credentials.write_text(
                json.dumps(
                    {
                        "host": "smtp.gmail.com",
                        "port": 587,
                        "user": "owner@example.com",
                        "password": "PASTE_APP_PASSWORD_HERE",
                        "from": "owner@example.com",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "placeholder"):
                import_smtp_credentials(credentials, root / ".env.v2")


if __name__ == "__main__":
    unittest.main()
