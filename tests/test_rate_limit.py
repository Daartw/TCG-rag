"""Límite de consultas al chat: no se puede saltar falsificando cabeceras ni rotando direcciones IPv6."""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src import api
from src.api import check_rate_limit, client_ip


def _request(headers: dict[str, str] | None = None, host: str = "203.0.113.9") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": (host, 1234), "method": "GET", "path": "/"})


@pytest.fixture
def limits(monkeypatch):
    def configure(per_ip: int, total: int = 0):
        monkeypatch.setattr(api, "CHAT_RATE_LIMIT_PER_MIN", per_ip)
        monkeypatch.setattr(api, "CHAT_GLOBAL_LIMIT_PER_MIN", total)
        api._hits.clear()
        api._global_hits.clear()

    yield configure
    api._hits.clear()
    api._global_hits.clear()


def test_ignores_forwarded_header_sent_by_the_client():
    # uvicorn ya resolvió la IP real (solo confía en proxies de redes privadas);
    # una cabecera inventada por el cliente no cambia su identidad
    assert client_ip(_request({"X-Forwarded-For": "1.2.3.4"})) == "203.0.113.9"
    assert client_ip(_request({"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})) == "203.0.113.9"
    assert client_ip(_request()) == "203.0.113.9"


def test_ipv6_addresses_are_grouped_by_their_64_network():
    a = client_ip(_request(host="2001:db8:abcd:12:1111:2222:3333:4444"))
    b = client_ip(_request(host="2001:db8:abcd:12:ffff:ffff:ffff:ffff"))
    other = client_ip(_request(host="2001:db8:abcd:13::1"))
    assert a == b == "2001:db8:abcd:12::/64"
    assert other != a
    assert client_ip(_request(host="::ffff:203.0.113.9")) == "203.0.113.9"
    assert client_ip(_request(host="testclient")) == "testclient"


def test_blocks_a_client_over_its_limit_even_with_spoofed_headers(limits):
    limits(per_ip=2)
    check_rate_limit(_request({"X-Forwarded-For": "1.1.1.1"}))
    check_rate_limit(_request({"X-Forwarded-For": "2.2.2.2"}))
    with pytest.raises(HTTPException) as blocked:
        check_rate_limit(_request({"X-Forwarded-For": "3.3.3.3"}))
    assert blocked.value.status_code == 429
    assert blocked.value.headers["Retry-After"] == "60"
    # otro cliente no se ve afectado
    check_rate_limit(_request(host="198.51.100.7"))


def test_global_cap_protects_the_llm_quota_across_many_clients(limits):
    limits(per_ip=5, total=3)
    for n in range(3):
        check_rate_limit(_request(host=f"198.51.100.{n}"))
    with pytest.raises(HTTPException) as blocked:
        check_rate_limit(_request(host="198.51.100.99"))
    assert blocked.value.status_code == 429


def test_limits_can_be_disabled(limits):
    limits(per_ip=0, total=0)
    for _ in range(50):
        check_rate_limit(_request())
    assert not api._hits and not api._global_hits
