import pytest
from unittest.mock import MagicMock, patch


class TestSchedulerSetup:
    def test_create_scheduler_returns_configured_scheduler(self):
        from app.scheduler import create_and_configure_scheduler

        job_func = MagicMock()
        scheduler = create_and_configure_scheduler(interval_minutes=30, job_func=job_func)

        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "sync_pipeline"

    def test_scheduler_job_has_correct_interval(self):
        from app.scheduler import create_and_configure_scheduler
        from apscheduler.triggers.interval import IntervalTrigger

        job_func = MagicMock()
        scheduler = create_and_configure_scheduler(interval_minutes=15, job_func=job_func)

        job = scheduler.get_jobs()[0]
        trigger = job.trigger
        # APScheduler 3.x: interval attribute; APScheduler 4.x: inspect repr
        interval_secs = getattr(trigger, "interval_length", None) or getattr(
            trigger, "interval", None
        )
        if interval_secs is not None:
            # APScheduler 3: interval is timedelta
            import datetime
            total_minutes = interval_secs.total_seconds() / 60 if hasattr(interval_secs, "total_seconds") else interval_secs / 60
            assert total_minutes == 15
        else:
            # Fall back: check string representation contains 15 minutes
            assert "15" in repr(trigger) or "0:15:00" in repr(trigger)

    def test_scheduler_job_points_to_job_func(self):
        from app.scheduler import create_and_configure_scheduler

        job_func = MagicMock(__name__="my_job")
        scheduler = create_and_configure_scheduler(interval_minutes=30, job_func=job_func)

        job = scheduler.get_jobs()[0]
        assert job.func is job_func

    def test_scheduler_start_and_shutdown_cleanly(self):
        from app.scheduler import create_and_configure_scheduler

        job_func = MagicMock()
        scheduler = create_and_configure_scheduler(interval_minutes=60, job_func=job_func)
        scheduler.start()
        scheduler.shutdown(wait=False)


class TestSyncStatus:
    @pytest.fixture(autouse=True)
    def reset_sync_state(self):
        import app.routers.sync as sync_mod
        sync_mod._last_sync_result = None
        yield
        sync_mod._last_sync_result = None

    def test_status_returns_none_before_any_sync(self, api_client):
        resp = api_client.get("/api/sync/status")
        assert resp.status_code == 200
        assert resp.json()["last_run"] is None

    def test_status_returns_result_after_post_sync(self, api_client, tmp_path, monkeypatch):
        api_client.post("/api/sync")

        resp = api_client.get("/api/sync/status")
        body = resp.json()
        assert body["last_run"] is not None
        assert "inserted" in body
        assert "skipped" in body
        assert "deleted" in body

    def test_status_reflects_latest_sync(self, api_client, tmp_path, monkeypatch):
        source = tmp_path / "src"
        source.mkdir()
        (source / "a.md").write_text("a")

        api_client.post("/api/folders", json={
            "host_path": str(source),
            "dest_subdir": "docs",
        })

        api_client.post("/api/sync")

        resp = api_client.get("/api/sync/status")
        assert resp.json()["inserted"] == 1


pytestmark_integration = pytest.mark.integration


class TestLifespanScheduler:
    def test_lifespan_starts_and_stops_scheduler(self):
        """Verify that app startup/shutdown doesn't raise."""
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.main.create_and_configure_scheduler") as mock_create:
            mock_scheduler = MagicMock()
            mock_create.return_value = mock_scheduler

            with TestClient(app):
                mock_scheduler.start.assert_called_once()

            mock_scheduler.shutdown.assert_called_once()
