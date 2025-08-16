import time
from typing import Optional
from gradio_client import Client

class GradioSpaceError(Exception):
    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

class SimilarityClient:
    def __init__(
        self,
        space_url: str,
        api_name: str = "/_on_click",
        timeout_s: int = 30,
        retries: int = 2,
        backoff_s: float = 1.5
    ):
        self.space_url = space_url
        self.api_name = api_name
        self.timeout_s = timeout_s
        self.retries = retries
        self.backoff_s = backoff_s

        try:
            # Initialize the Gradio Client but don't fail the whole app if Space is cold or unreachable
            self._client = Client(space_url)
        except Exception as e:
            # Instead of crashing during app init, keep client None and init later if needed
            self._client = None
            # Log warning (or you can print here if needed)
            print(f"[WARN] Gradio Client init failed: {e}. Will retry on demand.")

    def _ensure_client(self):
        """Ensure client is initialized before making any request."""
        if self._client is None:
            try:
                self._client = Client(self.space_url)
            except Exception as e:
                raise GradioSpaceError("Failed to initialize Gradio client.", detail=str(e))

    def healthcheck(self) -> bool:
        """Check if the HF Space API is accessible and responds with valid metadata."""
        try:
            self._ensure_client()
            api_info = self._client.view_api(self.api_name)
            return isinstance(api_info, dict)
        except Exception:
            return False

    def compare(self, lang: str, text1: str, text2: str) -> float:
        """
        Calls your Space's Gradio function. Current Space returns:
            (display_text, score)
        We extract index 1 (score).
        """
        self._ensure_client()
        last_err = None

        for attempt in range(self.retries + 1):
            try:
                result = self._client.predict(
                    lang,
                    text1,
                    text2,
                    api_name=self.api_name,
                    timeout=self.timeout_s
                )

                # Expected formats:
                # - Tuple/List: (display_text, score)
                # - Just float/int
                if isinstance(result, (list, tuple)) and len(result) >= 2:
                    return float(result[1])
                if isinstance(result, (float, int)):
                    return float(result)

                raise GradioSpaceError("Unexpected Space return format.", detail=str(result))

            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(self.backoff_s * (attempt + 1))
                else:
                    raise GradioSpaceError("Failed calling Gradio Space.", detail=str(e))

        raise GradioSpaceError("Unknown error after retries.", detail=str(last_err))
