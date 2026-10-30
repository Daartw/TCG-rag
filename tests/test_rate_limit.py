"""El límite de consultas al chat no se puede saltar falsificando X-Forwarded-For."""
from starlette.requests import Request

from src.api import client_ip


def _request(headers: dict[str, str], host: str = "10.0.0.5") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": (host, 1234), "method": "GET", "path": "/"})


def test_uses_ip_added_by_proxy_not_client_supplied_value():
    # el cliente envía una IP inventada; Caddy agrega la real al final
    req = _request({"X-Forwarded-For": "1.2.3.4, 203.0.113.9"})
    assert client_ip(req) == "203.0.113.9"


def test_single_forwarded_value_and_direct_connection():
    assert client_ip(_request({"X-Forwarded-For": "203.0.113.9"})) == "203.0.113.9"
    assert client_ip(_request({})) == "10.0.0.5"
    assert client_ip(_request({"X-Forwarded-For": " , "})) == "10.0.0.5"
