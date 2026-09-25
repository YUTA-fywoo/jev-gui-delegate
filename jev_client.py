"""Bounded, typed TypeSafe client. No GUI actions and no configurable network target."""
import asyncio
import json
import logging
import math
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal

import httpx2
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator
from typesafe_sdk import (AsyncTypeSafeClient, Choice, Noul, Score, RetryPolicy,
    TypeSafeAPIError, TypeSafeAPIConnectionError, TypeSafeAPITimeoutError,
    TypeSafeAPIResponseValidationError, TypeSafeError)
from credentials import resolve_key

ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://api.typesafe.ai"
JsonContent = str | dict[str, JsonValue] | list[JsonValue]
for _name in ("typesafe_sdk", "httpx2", "httpcore2"):
    logging.getLogger(_name).disabled = True
    logging.getLogger(_name).propagate = False
    logging.getLogger(_name).handlers = [logging.NullHandler()]

class BridgeError(Exception):
    def __init__(self, code, attempts=0):
        self.code, self.attempts = code, attempts
        super().__init__(code)

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

class ChoiceQuestion(StrictModel):
    type: Literal["choice"]
    instructions: JsonContent
    criteria: dict[str, JsonContent | None] = Field(min_length=2, max_length=255)

class NoulQuestion(StrictModel):
    type: Literal["noul"]
    instructions: JsonContent
    criteria: dict[Literal["true", "false"], JsonContent | None] | None = None

class ScoreQuestion(StrictModel):
    type: Literal["score"]
    instructions: JsonContent
    criteria: list[JsonContent] = Field(min_length=2, max_length=10)

Question = Annotated[ChoiceQuestion | NoulQuestion | ScoreQuestion, Field(discriminator="type")]

class EvaluationInput(StrictModel):
    state: JsonContent
    questions: dict[str, Question] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def limits(self):
        # Byte limits are conservative local guards, not claimed token limits.
        raw = json.dumps(self.model_dump(), ensure_ascii=False, allow_nan=False)
        if len(raw.encode("utf-8")) > 65536:
            raise ValueError("request too large")
        def depth(v, level=0):
            if level > 16:
                raise ValueError("nesting too deep")
            if isinstance(v, dict):
                for k, child in v.items():
                    if not k or len(k) > 256:
                        raise ValueError("invalid key")
                    depth(child, level + 1)
            elif isinstance(v, list):
                for child in v:
                    depth(child, level + 1)
        depth(self.model_dump())
        if not self.state or any(not q.instructions for q in self.questions.values()):
            raise ValueError("empty state/instructions")
        return self

class Settings(StrictModel):
    model: str = Field(pattern=r"^jev-(latest|preview|\d+\.\d+\.\d+)$")
    expected_model: str | None = Field(default=None, pattern=r"^jev-\d+\.\d+\.\d+$")
    calibrated: bool = False
    operation_timeout_seconds: float = Field(default=10.0, gt=0, le=15)
    total_timeout_seconds: float = Field(default=40.0, gt=0, le=50)
    max_retries: int = Field(default=2, ge=0, le=2)
    retry_budget_seconds: float = Field(default=25.0, gt=0, le=30)

    @model_validator(mode="after")
    def pin_calibration(self):
        if self.calibrated and (not self.expected_model or self.model != self.expected_model):
            raise ValueError("calibrated decisions require a pinned model")
        if self.total_timeout_seconds < self.operation_timeout_seconds:
            raise ValueError("total deadline shorter than operation timeout")
        return self

def load_settings(path=ROOT / "settings.json"):
    try:
        return Settings.model_validate_json(Path(path).read_text("utf-8"))
    except (ValueError, OSError):
        raise BridgeError("INVALID_CONFIG") from None

@contextmanager
def database(path=ROOT / "logs/usage.sqlite3"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=5)
    try:
        with con:
            con.execute("CREATE TABLE IF NOT EXISTS observations (requested TEXT PRIMARY KEY, actual TEXT NOT NULL)")
            con.execute("CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, time REAL, status TEXT, attempts INTEGER, milliseconds INTEGER, model TEXT, input_tokens INTEGER, output_tokens INTEGER)")
            yield con
    finally:
        con.close()

def record(path, request_id, status, attempts, started, response=None):
    model = response.model if response and re.fullmatch(r"jev-\d+\.\d+\.\d+", response.model) else None
    usage = response.usage if response else None
    with database(path) as con:
        con.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?)", (request_id, time.time(),
            status, attempts, int((time.monotonic()-started)*1000), model,
            usage.input_tokens if usage and type(usage.input_tokens) is int and usage.input_tokens >= 0 else None,
            usage.output_tokens if usage and type(usage.output_tokens) is int and usage.output_tokens >= 0 else None))

def statistics(path=ROOT / "logs/usage.sqlite3"):
    with database(path) as con:
        row = con.execute("SELECT COUNT(*),COALESCE(SUM(attempts),0),COALESCE(SUM(input_tokens),0),COALESCE(SUM(output_tokens),0) FROM calls").fetchone()
        return dict(zip(("calls", "http_attempts", "reported_input_tokens", "reported_output_tokens"), row))

def validate_response(response, request):
    def require(ok):
        if not ok:
            raise BridgeError("INVALID_RESPONSE")
    def probability(v):
        require(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1)
    require(bool(re.fullmatch(r"jev-\d+\.\d+\.\d+", response.model)))
    require(set(response.answers) == set(request.questions))
    for n in (response.usage.input_tokens, response.usage.output_tokens):
        require(type(n) is int and n >= 0)
    for key, q in request.questions.items():
        a = response.answers[key]
        require(a.type == q.type)
        if q.type == "noul":
            probability(a.noul)
            continue
        probability(a.confidence)
        for v in a.probabilities.values():
            probability(v)
        require(abs(sum(a.probabilities.values()) - 1) <= 0.005)
        if q.type == "choice":
            require(set(a.probabilities) == set(q.criteria))
            require(a.choice in q.criteria)
            require(a.probabilities[a.choice] >= max(a.probabilities.values()) - 0.00001)
        else:
            require(set(a.probabilities) == set(range(len(q.criteria))))
            require(a.legend == dict(enumerate(q.criteria)))
            require(math.isfinite(a.score) and 0 <= a.score <= len(q.criteria)-1)
            require(abs(a.score - sum(k*v for k,v in a.probabilities.items())) <= 0.01)

def guard_model(settings, actual, path):
    if settings.expected_model and actual != settings.expected_model:
        raise BridgeError("MODEL_VERSION_CHANGED")
    if re.fullmatch(r"jev-\d+\.\d+\.\d+", settings.model) and actual != settings.model:
        raise BridgeError("MODEL_VERSION_CHANGED")
    with database(path) as con:
        con.execute("INSERT OR IGNORE INTO observations VALUES (?,?)", (settings.model, actual))
        baseline = con.execute("SELECT actual FROM observations WHERE requested=?", (settings.model,)).fetchone()[0]
        if baseline != actual:
            raise BridgeError("MODEL_VERSION_CHANGED")

class JevClient:
    def __init__(self, *, settings=None, credential_resolver=resolve_key,
                 transport=None, usage_path=ROOT / "logs/usage.sqlite3"):
        self.settings = settings or load_settings()
        self.credential_resolver = credential_resolver
        self.transport = transport  # Test seam; never exposed in MCP or configuration.
        self.usage_path = usage_path

    async def evaluate(self, payload):
        started, request_id, attempts, response = time.monotonic(), uuid.uuid4().hex, 0, None
        status = "INTERNAL_ERROR"
        try:
            try:
                request = EvaluationInput.model_validate(payload)
            except (ValueError, TypeError, RecursionError):
                raise BridgeError("INVALID_INPUT") from None
            try:
                api_key, source = self.credential_resolver()
            except Exception:
                raise BridgeError("CREDENTIAL_STORE_UNAVAILABLE") from None
            if not api_key:
                raise BridgeError("MISSING_API_KEY")
            if not api_key.isascii() or any(c.isspace() for c in api_key):
                raise BridgeError("INVALID_API_KEY_FORMAT")
            async def count_attempt(_request):
                nonlocal attempts
                attempts += 1
            s = self.settings
            retry = RetryPolicy(max_retries=s.max_retries, timeout=s.retry_budget_seconds,
                backoff_initial=0.5, backoff_max=3, respect_retry_after=True)
            http = httpx2.AsyncClient(timeout=s.operation_timeout_seconds,
                transport=self.transport, event_hooks={"request": [count_attempt]},
                follow_redirects=False)
            async with asyncio.timeout(s.total_timeout_seconds):
                async with AsyncTypeSafeClient(api_key=api_key, model=s.model, base_url=ENDPOINT,
                    retry=retry, timeout=s.operation_timeout_seconds, http_client=http) as client:
                    classes = {"choice": Choice, "noul": Noul, "score": Score}
                    questions = {k: classes[q.type](**q.model_dump(exclude_none=True)) for k,q in request.questions.items()}
                    response = await client.system_one(state=request.state, questions=questions)
            validate_response(response, request)
            guard_model(s, response.model, self.usage_path)
            status = "OK"
            return {"ok": True, "request_id": request_id, "requested_model": s.model,
                "model": response.model, "answers": {k:v.model_dump(mode="json") for k,v in response.answers.items()},
                "usage": response.usage.model_dump(), "attempts": attempts,
                "credential_source": source, "calibrated": s.calibrated,
                "latency_ms": int((time.monotonic()-started)*1000)}
        except BridgeError as exc:
            status = exc.code
            raise BridgeError(status, attempts) from None
        except (TypeSafeAPITimeoutError, TimeoutError):
            status = "NETWORK_TIMEOUT"
            raise BridgeError(status, attempts) from None
        except TypeSafeAPIConnectionError:
            status = "NETWORK_ERROR"
            raise BridgeError(status, attempts) from None
        except TypeSafeAPIResponseValidationError:
            status = "INVALID_RESPONSE"
            raise BridgeError(status, attempts) from None
        except TypeSafeAPIError as exc:
            status = {401:"AUTHENTICATION_FAILED",403:"PERMISSION_DENIED",402:"BILLING_BLOCKED",
                422:"API_VALIDATION_FAILED",429:"RATE_LIMITED",529:"SERVICE_OVERLOADED"}.get(exc.status,"API_ERROR")
            raise BridgeError(status, attempts) from None
        except (TypeSafeError, ValidationError):
            status = "SDK_VALIDATION_FAILED"
            raise BridgeError(status, attempts) from None
        except Exception:
            status = "INTERNAL_ERROR"
            raise BridgeError(status, attempts) from None
        finally:
            # All logs are allowlisted scalars: no key, request state, rubric, answer, or exception text.
            try:
                record(self.usage_path, request_id, status, attempts, started, response)
            except Exception:
                logging.getLogger("jev-bridge").error("USAGE_RECORD_FAILED")

def health():
    try:
        s = load_settings()
        key, source = resolve_key()
        return {"ok": True, "service": "jev-bridge", "credential_available": bool(key),
            "credential_source": source, "api_verified": False,
            "note": "Local readiness only; evaluate verifies remote authentication.",
            "requested_model": s.model, "expected_model": s.expected_model,
            "calibrated": s.calibrated, "usage": statistics()}
    except BridgeError as exc:
        return {"ok": False, "error": exc.code}
    except Exception:
        return {"ok": False, "error": "LOCAL_HEALTH_FAILED"}

def capabilities():
    return {"service": "jev-bridge", "origin": "locally built integration, not a vendor MCP plugin",
        "transport": "stdio", "endpoint": ENDPOINT + "/v1/systemone",
        "question_types": ["choice", "noul", "score"], "input": "text or JSON",
        "max_questions": 32, "max_payload_bytes": 65536, "max_attempts": 3,
        "overall_deadline_seconds": 40, "retry_owner": "TypeSafe SDK only",
        "gui_execution": False, "arbitrary_code_execution": False,
        "images_supported": False, "calibration_required_before_autonomous_actions": True}
