import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch


class TestCachedReportGet(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("GROQ_API_KEY", "test-key")
        self._tmp_cache = tempfile.TemporaryDirectory()
        self._prev_cache_dir = os.environ.get("AUDIT_CACHE_DIR")
        os.environ["AUDIT_CACHE_DIR"] = self._tmp_cache.name

    def tearDown(self):
        if self._prev_cache_dir is None:
            os.environ.pop("AUDIT_CACHE_DIR", None)
        else:
            os.environ["AUDIT_CACHE_DIR"] = self._prev_cache_dir
        self._tmp_cache.cleanup()

    @contextmanager
    def _client(self):
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

    def test_get_audit_report_404_when_not_cached(self):
        with self._client() as client:
            r = client.get(
                "/audit/report",
                params={"url": "https://example.com"},
            )
        self.assertEqual(r.status_code, 404)
        body = r.json()
        self.assertIn("request_id", body)
        self.assertIn("error", body)

    def test_get_audit_report_200_when_cached(self):
        from backend.schemas.audit import AuditStatus, InsufficientDataReport

        stub = InsufficientDataReport(
            insufficient_data=True,
            url="https://example.com",
            audited_at=datetime.now(timezone.utc),
            status=AuditStatus.INSUFFICIENT_DATA,
            reason="test",
            pages_crawled=[],
            total_words_analysed=0,
        )

        import backend.main as main

        dummy_collection = SimpleNamespace(count=lambda: 0)
        dummy_chroma = SimpleNamespace(_collection=dummy_collection, get=lambda **_: {"ids": []})

        with patch.object(main, "load_fca_docs", return_value=dummy_chroma), patch.object(
            main,
            "get_retriever",
            return_value=SimpleNamespace(invoke=lambda *_: []),
        ), patch.object(main, "get_cached_report", return_value=stub):
            from fastapi.testclient import TestClient

            with TestClient(main.app) as client:
                r = client.get(
                    "/audit/report",
                    params={"url": "https://example.com"},
                )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("X-Cache"), "HIT")
        data = r.json()
        self.assertTrue(data.get("insufficient_data"))

    def test_metrics_endpoint(self):
        with self._client() as client:
            r = client.get("/metrics")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), dict)
        self.assertIn("timings_ms", r.json())


if __name__ == "__main__":
    unittest.main()
