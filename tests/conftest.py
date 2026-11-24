import pytest

from snelstart_mcp import vault


@pytest.fixture(autouse=True)
def test_vault(monkeypatch):
    records = {}

    class MemoryKeyring:
        def get_password(self, service, account):
            return records.get((service, account))

        def set_password(self, service, account, value):
            records[service, account] = value

    monkeypatch.setattr(vault, "backend", MemoryKeyring)
    return records
