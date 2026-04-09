import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch


class TestCachedReportGetSqliteIntegration(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("GROQ_API_KEY", "test-key")

    @contextmanager
    def _client(self, *, db_path: str):
        prev = os.environ.get("AUDIT_CACHE_DB_URL")
        os.environ["AUDIT_CACHE_DB_URL"] = f"sqlite:////{db_path.lstrip('/')}"

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
                try:
                    yield client
                finally:
                    if prev is None:
                        os.environ.pop("AUDIT_CACHE_DB_URL", None)
                    else:
                        os.environ["AUDIT_CACHE_DB_URL"] = prev

    def test_get_audit_report_reads_from_sqlite_cache(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "audit-cache.sqlite")
            url = "https://example.com"

            with self._client(db_path=db_path) as client:
                pv = client.get("/health").json()["pipeline_version"]

                from backend.cache.report_cache import cache_report
                from backend.schemas.audit import AuditStatus, InsufficientDataReport

                stub = InsufficientDataReport(
                    insufficient_data=True,
                    url=url,
                    audited_at=datetime.now(timezone.utc),
                    pipeline_version=pv,
                    status=AuditStatus.INSUFFICIENT_DATA,
                    reason="test",
                    pages_crawled=[],
                    total_words_analysed=0,
                )

                cache_report(url, stub)

                with sqlite3.connect(db_path) as conn:
                    n = conn.execute("SELECT COUNT(*) FROM audit_reports").fetchone()[0]
                self.assertEqual(n, 1)

                r = client.get("/audit/report", params={"url": url})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers.get("X-Cache"), "HIT")
                body = r.json()
                self.assertTrue(body.get("insufficient_data"))
                self.assertEqual(body.get("pipeline_version"), pv)


if __name__ == "__main__":
    unittest.main()

