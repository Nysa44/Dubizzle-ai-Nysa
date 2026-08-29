
import requests


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def health(self):
        r = requests.get(f"{self.base_url}/health", timeout=5)
        r.raise_for_status()
        return r.json()

    def chat(self, user_id, message, session_id=None):
        payload = {"user_id": user_id, "message": message}
        if session_id:
            payload["session_id"] = session_id
        r = requests.post(f"{self.base_url}/chat", json=payload, timeout=60)
        r.raise_for_status()
        return r.json()

    def memory(self, user_id):
        r = requests.get(f"{self.base_url}/users/{user_id}/memory", timeout=5)
        r.raise_for_status()
        return r.json()

    def favorite(self, user_id, listing_id):
        r = requests.post(f"{self.base_url}/users/{user_id}/favorites/{listing_id}", timeout=5)
        r.raise_for_status()
        return r.json()

    def unfavorite(self, user_id, listing_id):
        r = requests.delete(f"{self.base_url}/users/{user_id}/favorites/{listing_id}", timeout=5)
        r.raise_for_status()
        return r.json()
