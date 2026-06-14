import httpx


class LightRAGAuthError(Exception):
    pass


class LightRAGScanError(Exception):
    pass


class LightRAGClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: str | None = None

    @property
    def token(self) -> str | None:
        return self._token

    def login(self) -> None:
        try:
            resp = httpx.post(
                f"{self.base_url}/login",
                data={"username": self.username, "password": self.password},
            )
            resp.raise_for_status()
            self._token = resp.json()["access_token"]
        except Exception as exc:
            raise LightRAGAuthError(f"LightRAG login failed: {exc}") from exc

    def trigger_scan(self) -> None:
        if self._token is None:
            self.login()
        resp = httpx.post(
            f"{self.base_url}/documents/scan",
            headers={"Authorization": f"Bearer {self._token}"},
        )
        if resp.status_code == 401:
            self.login()
            resp = httpx.post(
                f"{self.base_url}/documents/scan",
                headers={"Authorization": f"Bearer {self._token}"},
            )
        try:
            resp.raise_for_status()
        except Exception as exc:
            raise LightRAGScanError(f"LightRAG scan failed: {exc}") from exc
