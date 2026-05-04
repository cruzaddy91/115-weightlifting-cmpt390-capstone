"""Thin HTTP client over the 115 Weightlifting API.

Designed to be imported by any simulation / load-test script in this toolkit
so common concerns (auth, headers, JSON envelope, idempotent register) are
written once.

IPv4 is forced via 127.0.0.1 by default because Node's DNS resolver (used by
the Vite dev proxy) prefers ::1 on macOS while Django's runserver binds
127.0.0.1 only. Same trap bit us in the frontend; same fix applies here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import sleep
from typing import Any, Callable, Optional

import requests


DEFAULT_API = "http://127.0.0.1:8000"


def _retry_on_throttle(make_request: Callable[[], requests.Response],
                       max_retries: int = 2) -> requests.Response:
    """Retry a request once or twice when the backend returns HTTP 429.

    The 115 Weightlifting API throttles /api/auth/register/ (10/min) and
    /api/auth/token/ (30/min) to defend against credential stuffing. That
    protection is correct in production but gets in the way of bulk-seeding
    demo data, so the sim client honors the server's Retry-After header and
    quietly waits it out.
    """
    attempt = 0
    while True:
        resp = make_request()
        if resp.status_code != 429 or attempt >= max_retries:
            return resp
        retry_after = resp.headers.get("Retry-After")
        delay = 2.0
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                pass
        # Cap the wait so a misconfigured throttle rate can't hang the tool.
        delay = min(delay, 20.0) + 0.5
        sleep(delay)
        attempt += 1


@dataclass
class ApiClient:
    base_url: str = DEFAULT_API
    session: requests.Session = field(default_factory=requests.Session)
    access_token: Optional[str] = None
    current_user: Optional[dict] = None

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    # -- internals -----------------------------------------------------------

    def _headers(self, extra: Optional[dict] = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if extra:
            headers.update(extra)
        return headers

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    # -- auth ---------------------------------------------------------------

    def register(
        self,
        username: str,
        password: str,
        user_type: str,
        coach_signup_code: Optional[str] = None,
    ) -> dict:
        body: dict[str, Any] = {
            "username": username,
            "password": password,
            "user_type": user_type,
        }
        if user_type == "coach" and coach_signup_code:
            body["coach_signup_code"] = coach_signup_code
        resp = _retry_on_throttle(
            lambda: self.session.post(self._url("/api/auth/register/"), json=body)
        )
        resp.raise_for_status()
        return resp.json()

    def login(self, username: str, password: str) -> dict:
        resp = _retry_on_throttle(
            lambda: self.session.post(
                self._url("/api/auth/token/"),
                json={"username": username, "password": password},
            )
        )
        resp.raise_for_status()
        tokens = resp.json()
        self.access_token = tokens["access"]
        me = self.session.get(self._url("/api/auth/me/"), headers=self._headers())
        me.raise_for_status()
        self.current_user = me.json()
        return tokens

    def register_or_login(
        self,
        username: str,
        password: str,
        user_type: str,
        coach_signup_code: Optional[str] = None,
    ) -> tuple[dict, bool]:
        """Ensure a user exists and we hold a live access token for them.

        Returns (user_record, created_bool). 'created' is True when we just
        registered; False when the user already existed and we logged in.
        """
        created = True
        try:
            self.register(username, password, user_type, coach_signup_code)
        except requests.HTTPError as exc:
            # 400 typically means 'already exists'; anything else re-raises.
            if exc.response is None or exc.response.status_code != 400:
                raise
            created = False
        self.login(username, password)
        assert self.current_user is not None  # mypy/typing hint
        return self.current_user, created

    def patch_me(self, payload: dict[str, Any]) -> dict:
        """PATCH /api/auth/me/ (athlete profile: bodyweight_kg, gender)."""
        resp = self.session.patch(
            self._url("/api/auth/me/"),
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        body = resp.json()
        self.current_user = body
        return body

    # -- resources ----------------------------------------------------------

    def list_athletes(self, scope: str = "all", q: str = "", page: int = 1) -> dict:
        resp = self.session.get(
            self._url("/api/auth/athletes/"),
            params={"scope": scope, "q": q, "page": page},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def create_program(self, payload: dict) -> dict:
        resp = self.session.post(
            self._url("/api/programs/"),
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def update_program(self, program_id: int, payload: dict) -> dict:
        resp = self.session.patch(
            self._url(f"/api/programs/{program_id}/"),
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def assign_program(self, program_id: int, athlete_id: int) -> dict:
        resp = self.session.patch(
            self._url(f"/api/programs/{program_id}/assign/"),
            json={"athlete_id": athlete_id},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def list_programs(self) -> list[dict]:
        resp = self.session.get(
            self._url("/api/programs/"),
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def update_program_completion(self, program_id: int, completion_data: dict) -> dict:
        resp = self.session.patch(
            self._url(f"/api/athletes/program-completion/{program_id}/"),
            json={"completion_data": completion_data},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def create_personal_record(self, lift_type: str, weight: str, date: str) -> dict:
        resp = self.session.post(
            self._url("/api/athletes/prs/"),
            json={"lift_type": lift_type, "weight": weight, "date": date},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def create_workout_log(self, date: str, notes: str = "") -> dict:
        resp = self.session.post(
            self._url("/api/athletes/workouts/"),
            json={"date": date, "notes": notes},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()
