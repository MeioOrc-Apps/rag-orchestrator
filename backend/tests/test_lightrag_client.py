import pytest
from unittest.mock import patch, MagicMock


class TestLogin:
    def test_login_posts_credentials_and_stores_token(self):
        from app.lightrag_client import LightRAGClient

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "tok123"}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            client = LightRAGClient("http://lightrag:9621", "sergio", "secret")
            client.login()

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "/login" in call_args.args[0]
        assert call_args.kwargs["data"]["username"] == "sergio"
        assert call_args.kwargs["data"]["password"] == "secret"
        assert client.token == "tok123"

    def test_login_raises_on_bad_credentials(self):
        from app.lightrag_client import LightRAGClient, LightRAGAuthError

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = Exception("401 Unauthorized")

        with patch("httpx.post", return_value=mock_resp):
            client = LightRAGClient("http://lightrag:9621", "bad", "creds")
            with pytest.raises(LightRAGAuthError):
                client.login()


class TestTriggerScan:
    def _make_client_with_token(self, token="valid_token"):
        from app.lightrag_client import LightRAGClient
        client = LightRAGClient("http://lightrag:9621", "sergio", "secret")
        client._token = token
        return client

    def test_trigger_scan_sends_bearer_token(self):
        from app.lightrag_client import LightRAGClient

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        client = self._make_client_with_token("mytoken")
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            client.trigger_scan()

        call_args = mock_post.call_args
        assert "/documents/scan" in call_args.args[0]
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer mytoken"

    def test_trigger_scan_logins_first_if_no_token(self):
        from app.lightrag_client import LightRAGClient

        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {"access_token": "newtoken"}
        login_resp.raise_for_status = MagicMock()

        scan_resp = MagicMock()
        scan_resp.status_code = 200
        scan_resp.raise_for_status = MagicMock()

        client = LightRAGClient("http://lightrag:9621", "sergio", "secret")
        with patch("httpx.post", side_effect=[login_resp, scan_resp]) as mock_post:
            client.trigger_scan()

        assert mock_post.call_count == 2
        assert client.token == "newtoken"

    def test_trigger_scan_relogins_on_401_and_retries(self):
        from app.lightrag_client import LightRAGClient

        scan_401 = MagicMock(status_code=401)
        scan_401.raise_for_status = MagicMock()

        login_resp = MagicMock(status_code=200)
        login_resp.json.return_value = {"access_token": "refreshed"}
        login_resp.raise_for_status = MagicMock()

        scan_ok = MagicMock(status_code=200)
        scan_ok.raise_for_status = MagicMock()

        client = self._make_client_with_token("expired")
        with patch("httpx.post", side_effect=[scan_401, login_resp, scan_ok]):
            client.trigger_scan()

        assert client.token == "refreshed"

    def test_trigger_scan_raises_after_second_401(self):
        from app.lightrag_client import LightRAGClient, LightRAGScanError

        scan_401 = MagicMock(status_code=401)
        scan_401.raise_for_status = MagicMock()

        login_resp = MagicMock(status_code=200)
        login_resp.json.return_value = {"access_token": "new"}
        login_resp.raise_for_status = MagicMock()

        scan_401_again = MagicMock(status_code=401)
        scan_401_again.raise_for_status.side_effect = Exception("401")

        client = self._make_client_with_token("bad")
        with patch("httpx.post", side_effect=[scan_401, login_resp, scan_401_again]):
            with pytest.raises(LightRAGScanError):
                client.trigger_scan()
