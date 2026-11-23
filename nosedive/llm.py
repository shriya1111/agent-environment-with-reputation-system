"""Unified chat client for OpenAI-compatible endpoints.

Backends:
  - "local:<alias>"       -> local llama-cpp-python server (OpenAI API), free + unlimited
  - "openrouter:<model>"  -> https://openrouter.ai (free models or paid with credits)
  - "anthropic:<model>"   -> Anthropic Messages API (needs ANTHROPIC_API_KEY)

Every call returns (parsed_json_or_None, raw_text, meta).
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

LOCAL_URL = os.environ.get("NOSEDIVE_LOCAL_URL", "http://127.0.0.1:8080/v1/chat/completions")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

_LOCAL = requests.Session()
_LOCAL.trust_env = False  # never route localhost through the egress proxy

USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "errors": 0}


def extract_json(text: str):
    """Best-effort JSON extraction from model output."""
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None


def chat(model: str, system: str, user: str, max_tokens: int = 600, temperature: float = 0.8,
         schema: dict | None = None, retries: int = 3, timeout: int = 600):
    backend, _, name = model.partition(":")
    if backend != "local":
        # Remote models often reason in plain text before the JSON; a strict compute cap would just
        # truncate them. The compute->token cap is enforced exactly only for local models.
        max_tokens = max(max_tokens, int(os.environ.get("NOSEDIVE_REMOTE_MIN_TOKENS", 8000)))
        retries = min(retries, 2)  # free tier: 50 requests/day, don't burn them on retries
    last_err = None
    for attempt in range(retries):
        try:
            t0 = time.time()
            if backend == "anthropic":
                r = requests.post(
                    ANTHROPIC_URL,
                    headers={"x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
                             "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": name, "max_tokens": max_tokens, "temperature": temperature,
                          "system": system, "messages": [{"role": "user", "content": user}]},
                    timeout=timeout)
                r.raise_for_status()
                d = r.json()
                text = "".join(b.get("text", "") for b in d.get("content", []))
                usage = {"prompt_tokens": d["usage"]["input_tokens"],
                         "completion_tokens": d["usage"]["output_tokens"]}
            else:
                url = LOCAL_URL if backend == "local" else OPENROUTER_URL
                headers = {"Content-Type": "application/json"}
                if backend == "openrouter":
                    headers["Authorization"] = "Bearer " + os.environ.get("OPENROUTER_API_KEY", "proxy-injected")
                body = {"model": name, "max_tokens": max_tokens, "temperature": temperature,
                        "messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": user}]}
                if schema and backend == "local":
                    # grammar-constrained decoding guarantees valid JSON for small models
                    body["response_format"] = {"type": "json_object", "schema": schema}
                poster = _LOCAL.post if backend == "local" else requests.post
                r = poster(url, headers=headers, json=body, timeout=timeout)
                if r.status_code == 429:
                    time.sleep(15 * (attempt + 1))
                    last_err = r.text[:200]
                    continue
                r.raise_for_status()
                d = r.json()
                if "choices" not in d:
                    raise RuntimeError(str(d)[:300])
                msg = d["choices"][0]["message"]
                text = msg.get("content") or ""
                reasoning = msg.get("reasoning") or ""
                usage = d.get("usage") or {}
                parsed = extract_json(text) or (extract_json(reasoning[-3000:]) if reasoning else None)
                USAGE["calls"] += 1
                USAGE["prompt_tokens"] += usage.get("prompt_tokens", 0) or 0
                USAGE["completion_tokens"] += usage.get("completion_tokens", 0) or 0
                return parsed, text, {"latency": round(time.time() - t0, 2), "usage": usage,
                                      "reasoning": reasoning}
            USAGE["calls"] += 1
            USAGE["prompt_tokens"] += usage.get("prompt_tokens", 0) or 0
            USAGE["completion_tokens"] += usage.get("completion_tokens", 0) or 0
            return extract_json(text), text, {"latency": round(time.time() - t0, 2), "usage": usage}
        except Exception as e:  # noqa: BLE001
            last_err = repr(e)[:300]
            time.sleep(3 * (attempt + 1))
    USAGE["errors"] += 1
    return None, "", {"error": last_err}
