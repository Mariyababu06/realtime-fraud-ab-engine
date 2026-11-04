import logging
from pipeline.logging_config import RedactPIIFilter, redact


def test_redacts_account_email_phone_and_secret():
    text = redact("acct C123456789 email a.person@example.com phone +1 415 555 0198 token=abc123")
    assert "C123456789" not in text
    assert "a.person@example.com" not in text
    assert "abc123" not in text
    assert "[REDACTED" in text


def test_redacts_nested_structured_fields():
    assert "M123456789" not in str(redact({"ctx": {"account": "M123456789"}}))


def test_escapes_newlines():
    assert "\\n" in redact("hello\nforged log line")


def test_filter_cleans_formatted_message():
    record = logging.LogRecord("x", logging.INFO, "", 0, "account %s", ("C123456789",), None)
    RedactPIIFilter().filter(record)
    assert "C123456789" not in record.getMessage()


def test_secret_key_redacted_case_insensitive():
    assert "topsecret" not in redact("PASSWORD:topsecret")
