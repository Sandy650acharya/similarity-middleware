import time
from typing import Optional, Tuple
from gradio_client import Client, handle_file

class GradioSpaceError(Exception):
    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

class SimilarityClient:
    def __init__(self, space_url: str, api_name: str = "/_on_click", timeout_s: int = 30, retries: int = 2, backoff_s: float = 1.5):
        self.space_url = space_url
        self.api_name = api_name
        self.timeout_s = timeout_s
        self.retries = retries
        self.backoff_s = backoff_s
        self._client = Client(space_url)

    def healthcheck(self) -> bool:
        try:
            # a lightweight no-op call: fetch config
            _ = self._client.view_api(self.api_name)
            return True
        except Exception:
            return False

    def compare(self, lang: str, text1: str, text2: str) -> float:
        """
        Calls your Space's Gradio function. Your current test.py shows:
            result = client.predict(lang, text1, text2, api_name="/_on_click")
            _, similarity = result
        So we keep the same contract: returns a tuple or list where index 1 is the score.
        """
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
                # Expecting something like (display_text, score) or [display_text, score]
                if isinstance(result, (list, tuple)) and len(result) >= 2:
                    return float(result[1])
                # If the Space returns just the float:
                if isinstance(result, (float, int)):
                    return float(result)
                raise GradioSpaceError("Unexpected Space return format.", detail=str(result))
            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(self.backoff_s * (attempt + 1))
                else:
                    raise GradioSpaceError("Failed calling Gradio Space.", detail=str(e))
        # Should not reach here
        raise GradioSpaceError("Unknown error", detail=str(last_err))
