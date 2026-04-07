import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch


class TestRequestIdIntegration(unittest.TestCase):
    def setUp(self):
        # Lifespan requires GROQ_API_KEY to be set.
        os.environ.setdefault("GROQ_API_KEY", "test-key")

    @contextmanager
    def _client(self):
        # Patch heavy startup dependencies so tests are fast and offline.
        import backend.main as main

        dummy_collection = SimpleNamespace(count=lambda: 0)
        dummy_chroma = SimpleNamespace(_collection=dummy_collection, get=lambda **_: {"ids": []})

        with patch.object(main, "load_fca_docs", return_value=dummy_chroma), patch.object(
            main,
            "get_retriever",
            return_value=SimpleNamespace(invoke=lambda *_: []),
        ):
            from fastapi.testclient import TestClient

            with TestClient(main.app) as client:
                yield client

    def test_request_id_present_on_200(self):
        with self._client() as client:
            r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertIn("X-Request-ID", r.headers)
        self.assertTrue(r.headers["X-Request-ID"])

    def test_request_id_present_on_422(self):
        with self._client() as client:
            r = client.post("/audit", json={"url": "ftp://example.com"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("X-Request-ID", r.headers)
        body = r.json()
        self.assertIn("request_id", body)
        self.assertEqual(body["request_id"], r.headers["X-Request-ID"])


if __name__ == "__main__":
    unittest.main()

