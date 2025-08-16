import time
from typing import Optional
from gradio_client import Client

class GradioSpaceError(Exception):
    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

class SimilarityClient:
    def __init__(self, space_url: str, api_name: str = "/_on_click",
                 timeout_s: int = 30, retries: int = 3, backoff_s: float = 2.0):
        self.space_url = space_url
        self.api_name = api_name
        self.timeout_s = timeout_s
        self.retries = retries
        self.backoff_s = backoff_s
        self._client = None

    def _initialize_client(self):
        """Attempt to initialize the Gradio client with retries."""
        last_err = None
        for attempt in range(self.retries + 1):
            try:
                client = Client(self.space_url)
                # Confirm API info exists
                _ = client.view_api(self.api_name)
                self._client = client
                return
            except Exception as e:
                last_err = e
                time.sleep(self.backoff_s * (attempt + 1))
        raise GradioSpaceError("Failed to initialize Gradio client after retries", detail=str(last_err))

    def _ensure_client(self):
        if self._client is None:
            self._initialize_client()

    def healthcheck(self) -> bool:
        try:
            self._ensure_client()
            return True
        except GradioSpaceError:
            return False

    def compare(self, lang: str, text1: str, text2: str) -> float:
        self._ensure_client()
        last_err = None
        for attempt in range(self.retries + 1):
            try:
                result = self._client.predict(
                    lang, text1, text2,
                    api_name=self.api_name, timeout=self.timeout_s
                )
                if isinstance(result, (list, tuple)) and len(result) >= 2:
                    return float(result[1])
                if isinstance(result, (float, int)):
                    return float(result)
                raise GradioSpaceError("Unexpected return format", detail=str(result))
            except Exception as e:
                last_err = e
                time.sleep(self.backoff_s * (attempt + 1)) if attempt < self.retries else None

        raise GradioSpaceError("Failed after retries", detail=str(last_err))
