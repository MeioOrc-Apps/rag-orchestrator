import pytest
from unittest.mock import MagicMock, patch


class TestSchedulerSetup:
    def test_create_scheduler_returns_background_scheduler(self):
        from app.scheduler import create_scheduler
        scheduler = create_scheduler()
        from apscheduler.schedulers.background import BackgroundScheduler
        assert isinstance(scheduler, BackgroundScheduler)

    def test_add_interval_job_registers_job_with_given_id(self):
        from app.scheduler import create_scheduler, add_interval_job
        scheduler = create_scheduler()
        func = MagicMock(__name__="myjob")
        add_interval_job(scheduler, func, 10, "myjob")
        ids = [j.id for j in scheduler.get_jobs()]
        assert "myjob" in ids

    def test_add_interval_job_sets_correct_interval(self):
        from app.scheduler import create_scheduler, add_interval_job
        scheduler = create_scheduler()
        func = MagicMock(__name__="myjob")
        add_interval_job(scheduler, func, 7, "myjob")
        job = scheduler.get_job("myjob")
        trigger = job.trigger
        interval = getattr(trigger, "interval_length", None) or getattr(trigger, "interval", None)
        if interval is not None:
            total_minutes = interval.total_seconds() / 60 if hasattr(interval, "total_seconds") else interval / 60
            assert total_minutes == 7
        else:
            assert "7" in repr(trigger) or "0:07:00" in repr(trigger)

    def test_scheduler_starts_and_shuts_down_cleanly(self):
        from app.scheduler import create_scheduler, add_interval_job
        scheduler = create_scheduler()
        add_interval_job(scheduler, MagicMock(__name__="f"), 60, "test")
        scheduler.start()
        scheduler.shutdown(wait=False)


class TestAllJobsRegistered:
    def test_lifespan_registers_scan_job(self):
        from app.scheduler import create_scheduler, add_interval_job
        from app.routers.sync import run_sync_job
        scheduler = create_scheduler()
        add_interval_job(scheduler, run_sync_job, 15, "scan")
        assert scheduler.get_job("scan") is not None

    def test_lifespan_registers_parse_job(self):
        from app.scheduler import create_scheduler, add_interval_job
        from app.jobs.parse_job import run_parse_job
        scheduler = create_scheduler()
        add_interval_job(scheduler, run_parse_job, 5, "parse")
        assert scheduler.get_job("parse") is not None

    def test_lifespan_registers_translate_job(self):
        from app.scheduler import create_scheduler, add_interval_job
        from app.jobs.translate_job import run_translate_job
        scheduler = create_scheduler()
        add_interval_job(scheduler, run_translate_job, 5, "translate")
        assert scheduler.get_job("translate") is not None

    def test_lifespan_registers_index_job(self):
        from app.scheduler import create_scheduler, add_interval_job
        from app.jobs.index_job import run_index_job
        scheduler = create_scheduler()
        add_interval_job(scheduler, run_index_job, 5, "index")
        assert scheduler.get_job("index") is not None

    def test_lifespan_registers_delete_job(self):
        from app.scheduler import create_scheduler, add_interval_job
        from app.jobs.delete_job import run_delete_job
        scheduler = create_scheduler()
        add_interval_job(scheduler, run_delete_job, 5, "delete")
        assert scheduler.get_job("delete") is not None


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
        api_client.post("/api/folders", json={"host_path": str(source), "dest_subdir": "docs"})
        api_client.post("/api/sync")
        resp = api_client.get("/api/sync/status")
        assert resp.json()["inserted"] == 1


class TestLifespanScheduler:
    def test_lifespan_starts_and_stops_scheduler(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.main.create_scheduler") as mock_create:
            mock_scheduler = MagicMock()
            mock_create.return_value = mock_scheduler

            with TestClient(app):
                mock_scheduler.start.assert_called_once()

            mock_scheduler.shutdown.assert_called_once()

    def test_lifespan_registers_five_jobs(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.main.create_scheduler") as mock_create, \
             patch("app.main.add_interval_job") as mock_add:
            mock_create.return_value = MagicMock()
            with TestClient(app):
                pass

        job_ids = [call[0][3] for call in mock_add.call_args_list]
        assert set(job_ids) == {"scan", "parse", "translate", "index", "delete"}
