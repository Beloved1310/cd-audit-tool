import os
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch


class TestSqliteCacheEndpointsIntegration(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("GROQ_API_KEY", "test-key")

    @contextmanager
    def _client(self, *, db_path: str):
        prev_db_url = os.environ.get("AUDIT_CACHE_DB_URL")
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
                    if prev_db_url is None:
                        os.environ.pop("AUDIT_CACHE_DB_URL", None)
                    else:
                        os.environ["AUDIT_CACHE_DB_URL"] = prev_db_url

    def _seed_report(self, *, client, url: str):
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
        return pv

    def test_post_audit_returns_hit_and_does_not_run_pipeline_when_cached(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "audit-cache.sqlite")
            url = "https://example.com"

            with self._client(db_path=db_path) as client:
                pv = self._seed_report(client=client, url=url)

                import backend.main as main

                with patch.object(main, "get_or_run_audit", side_effect=AssertionError("pipeline ran")):
                    r = client.post("/audit", json={"url": url})

                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers.get("X-Cache"), "HIT")
                body = r.json()
                self.assertTrue(body.get("insufficient_data"))
                self.assertEqual(body.get("pipeline_version"), pv)

    def test_delete_cache_removes_sqlite_row_and_subsequent_get_misses(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "audit-cache.sqlite")
            url = "https://example.com"

            with self._client(db_path=db_path) as client:
                self._seed_report(client=client, url=url)

                r1 = client.get("/audit/report", params={"url": url})
                self.assertEqual(r1.status_code, 200)

                d = client.delete("/audit/cache", params={"url": url})
                self.assertEqual(d.status_code, 200)
                self.assertEqual(d.json().get("deleted"), 1)

                r2 = client.get("/audit/report", params={"url": url})
                self.assertEqual(r2.status_code, 404)

    def test_concurrent_post_audit_overlap_returns_409_for_second_request(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "audit-cache.sqlite")
            url = "https://example.com"

            import backend.main as main
            from backend.schemas.audit import AuditStatus, InsufficientDataReport

            def slow_audit(**_):
                time.sleep(0.4)
                return InsufficientDataReport(
                    insufficient_data=True,
                    url=url,
                    audited_at=datetime.now(timezone.utc),
                    pipeline_version="pv",
                    status=AuditStatus.INSUFFICIENT_DATA,
                    reason="test",
                    pages_crawled=[],
                    total_words_analysed=0,
                )

            with patch.object(main, "get_or_run_audit", side_effect=slow_audit):
                results: list[int] = []
                barrier = threading.Barrier(3)

                def worker():
                    with self._client(db_path=db_path) as client:
                        barrier.wait()
                        r = client.post("/audit", json={"url": url})
                        results.append(r.status_code)

                t1 = threading.Thread(target=worker)
                t2 = threading.Thread(target=worker)
                t1.start()
                t2.start()
                barrier.wait()
                t1.join()
                t2.join()

                self.assertCountEqual(results, [200, 409])


if __name__ == "__main__":
    unittest.main()

