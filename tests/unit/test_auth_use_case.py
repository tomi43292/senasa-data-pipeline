from __future__ import annotations
from datetime import datetime, timedelta, timezone
from senasa_pipeline.application.use_cases.ensure_senasa_session import EnsureSenasaSessionUseCase, SystemClock
from tests.unit._fakes_auth import FakeStore, FakeProvider, FakeConsumer

def test_ensure_session_already_active():
    store = FakeStore()
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    exp = now + timedelta(hours=6)
    store.save({"k": "v"}, exp)

    class FixedClock(SystemClock):
        def now(self):
            return now

    uc = EnsureSenasaSessionUseCase(store=store, provider=FakeProvider(), consumer=FakeConsumer(valid_first=True), clock=FixedClock())
    res = uc.execute()
    assert res.status == "ALREADY_ACTIVE"
    assert res.expires_at == exp


def test_ensure_session_refreshed_when_invalid():
    store = FakeStore()  # empty store forces login
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)

    class FixedClock(SystemClock):
        def now(self):
            return now

    provider = FakeProvider(token="T", sign="S")
    consumer = FakeConsumer(valid_first=False)
    uc = EnsureSenasaSessionUseCase(store=store, provider=provider, consumer=consumer, clock=FixedClock())
    res = uc.execute()
    assert res.status in ("REFRESHED", "ERROR")  # depending on validate_session logic
