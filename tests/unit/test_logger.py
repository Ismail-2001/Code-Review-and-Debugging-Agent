"""Tests for secret-masking logger."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import logging

from utils.logger import SecretMasker


class TestSecretMasker:
    def setup_method(self):
        self.masker = SecretMasker()
        self.logger = logging.getLogger("test")
        self.logger.addFilter(self.masker)

    def test_masks_openai_key(self):
        record = self.logger.makeRecord(
            "test",
            logging.INFO,
            "",
            0,
            "Using key sk-1234567890123456789012345678901234567890",
            (),
            None,
        )
        assert self.masker.filter(record)
        assert "sk-********" in record.msg
        assert "1234567890" not in record.msg

    def test_masks_key_parameter(self):
        record = self.logger.makeRecord(
            "test",
            logging.INFO,
            "",
            0,
            "api_key=my-super-secret-key-12345",
            (),
            None,
        )
        assert self.masker.filter(record)
        assert "********" in record.msg
        assert "my-super-secret" not in record.msg

    def test_passes_through_normal_messages(self):
        record = self.logger.makeRecord(
            "test",
            logging.INFO,
            "",
            0,
            "Normal log message",
            (),
            None,
        )
        assert self.masker.filter(record)
        assert record.msg == "Normal log message"
