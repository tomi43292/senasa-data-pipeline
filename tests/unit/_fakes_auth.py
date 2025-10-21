from __future__ import annotations
from typing import Protocol

class FakeStore:
    def __init__(self) -> None:
        self._cookies: dict[str, str] = {}
        self._exp = None
        self._active = False
    def load(self):
        return dict(self._cookies), self._exp, self._active
    def save(self, cookies, exp):
        self._cookies = dict(cookies)
        self._exp = exp
        self._active = True
    def mark_inactive(self):
        self._active = False

class FakeProvider:
    def __init__(self, token="tok", sign="sig") -> None:
        self.token, self.sign = token, sign
        self.called = 0
    def get_token_sign(self):
        self.called += 1
        return self.token, self.sign

class FakeConsumer:
    def __init__(self, valid_first=True) -> None:
        self.valid_first = valid_first
        self.cookies = {"cookie": "value"}
        self._validated = False
    def validate_session(self) -> bool:
        if not self._validated:
            self._validated = True
            return self.valid_first
        return True
    def login_with_token_sign(self, token, sign):
        self.cookies = {"session": "abc"}
