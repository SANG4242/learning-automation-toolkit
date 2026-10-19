import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("asr_service", ROOT / "tools/media/asr_service.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)

class ServiceTests(unittest.TestCase):
    def test_existing_service_does_not_launch(self):
        with patch.object(service, "health", return_value=True), patch.object(service.subprocess, "Popen") as launch:
            self.assertEqual(service.ensure_service("http://localhost:8000/", True), "http://localhost:8000")
            launch.assert_not_called()

    def test_explicit_endpoint_does_not_launch(self):
        with patch.object(service, "health", return_value=False), patch.object(service.subprocess, "Popen") as launch:
            self.assertIsNone(service.ensure_service("http://example.test:8000", False))
            launch.assert_not_called()

    def test_wsl_fallback(self):
        with patch.object(service, "health", side_effect=[False, True]), patch.object(service, "wsl_url", return_value="http://172.20.0.2:8000"), patch.object(service.subprocess, "Popen") as launch:
            self.assertEqual(service.ensure_service("http://localhost:8000", True), "http://172.20.0.2:8000")
            launch.assert_not_called()

    def test_disabled_auto_start(self):
        with patch.object(service, "health", return_value=False), patch.object(service, "wsl_url", return_value=None), patch.dict(os.environ, {"QWEN_ASR_AUTO_START": "0"}), patch.object(service.subprocess, "Popen") as launch:
            self.assertIsNone(service.ensure_service("http://localhost:8000", True))
            launch.assert_not_called()

    def test_unmanaged_stop_rejected(self):
        with patch.object(service, "DATA_DIR", ROOT / ".local" / "nonexistent-service-test"):
            with self.assertRaisesRegex(RuntimeError, "没有本工具管理"):
                service.stop_managed_service()

if __name__ == "__main__":
    unittest.main()
