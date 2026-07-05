from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol
from urllib import parse, request


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    payload: dict[str, Any]


class HttpClient(Protocol):
    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
        auth: tuple[str, str] | None = None,
    ) -> HttpResponse:
        ...

    def post_form(
        self,
        url: str,
        *,
        data: dict[str, str],
        auth: tuple[str, str] | None = None,
    ) -> HttpResponse:
        ...


class UrllibHttpClient:
    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
        auth: tuple[str, str] | None = None,
    ) -> HttpResponse:
        body = json.dumps(payload).encode("utf-8")
        all_headers = {"Content-Type": "application/json", **headers}
        req = request.Request(url, data=body, headers=all_headers, method="POST")
        if auth is not None:
            req.add_header("Authorization", _basic_auth(*auth))
        with request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8")
            return HttpResponse(response.status, json.loads(text) if text else {})

    def post_form(
        self,
        url: str,
        *,
        data: dict[str, str],
        auth: tuple[str, str] | None = None,
    ) -> HttpResponse:
        body = parse.urlencode(data).encode("utf-8")
        req = request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        if auth is not None:
            req.add_header("Authorization", _basic_auth(*auth))
        with request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8")
            return HttpResponse(response.status, json.loads(text) if text else {})


def _basic_auth(username: str, password: str) -> str:
    import base64

    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"
