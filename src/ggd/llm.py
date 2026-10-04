"""Model abstraction.

The agent code only talks to `LLM.chat`, so swapping Ollama for another backend
(vLLM on Kaggle, an OpenAI-compatible server, ...) means adding one subclass.
Standard library only, to keep the reproduction footprint minimal.
"""

from __future__ import annotations

import json
import os
import time
import tomllib
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "model.toml"


@dataclass
class ModelConfig:
    backend: str
    name: str
    host: str
    num_ctx: int
    temperature: float
    top_p: float
    seed: int
    num_predict: int
    think: bool
    keep_alive: str

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG) -> "ModelConfig":
        cfg = tomllib.loads(path.read_text())
        m, inf = cfg["model"], cfg["inference"]
        env = os.environ.get
        return cls(
            backend=env("GGD_BACKEND", m["backend"]),
            name=env("GGD_MODEL", m["name"]),
            host=env("GGD_OLLAMA_HOST", m["host"]),
            num_ctx=int(env("GGD_NUM_CTX", inf["num_ctx"])),
            temperature=float(env("GGD_TEMPERATURE", inf["temperature"])),
            top_p=float(inf["top_p"]),
            seed=int(env("GGD_SEED", inf["seed"])),
            num_predict=int(inf["num_predict"]),
            think=env("GGD_THINK", str(inf["think"])).lower() == "true",
            keep_alive=inf["keep_alive"],
        )


@dataclass
class ChatResult:
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    thinking: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    wall_s: float = 0.0
    gen_tok_per_s: float = 0.0


class LLM:
    def __init__(self, cfg: ModelConfig | None = None):
        self.cfg = cfg or ModelConfig.load()

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             **overrides) -> ChatResult:
        raise NotImplementedError


class OllamaLLM(LLM):
    def chat(self, messages, tools=None, **overrides):
        c = self.cfg
        body = {
            "model": c.name,
            "messages": messages,
            "stream": False,
            "think": overrides.pop("think", c.think),
            "keep_alive": c.keep_alive,
            "options": {
                "num_ctx": c.num_ctx,
                "temperature": c.temperature,
                "top_p": c.top_p,
                "seed": c.seed,
                "num_predict": c.num_predict,
                **overrides,
            },
        }
        if tools:
            body["tools"] = tools
        req = urllib.request.Request(
            f"{c.host}/api/chat", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=3600) as r:
            out = json.loads(r.read())
        wall = time.time() - t0
        msg = out.get("message", {})
        ev, ed = out.get("eval_count", 0), out.get("eval_duration", 0)
        return ChatResult(
            content=msg.get("content", ""),
            tool_calls=msg.get("tool_calls", []) or [],
            thinking=msg.get("thinking", "") or "",
            prompt_tokens=out.get("prompt_eval_count", 0),
            completion_tokens=ev,
            wall_s=wall,
            gen_tok_per_s=(ev / (ed / 1e9)) if ed else 0.0,
        )


class OpenAICompatLLM(LLM):
    """OpenAI-compatible /v1/chat/completions (vLLM on Kaggle). Converts Ollama-style
    messages (tool results with `tool_name`) to OpenAI format and tool calls back."""

    def chat(self, messages, tools=None, **overrides):
        c = self.cfg
        msgs, last_ids = [], []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                calls = []
                for i, tc in enumerate(m["tool_calls"]):
                    f = tc["function"]
                    cid = tc.get("id") or f"call_{len(msgs)}_{i}"
                    calls.append({"id": cid, "type": "function", "function": {
                        "name": f["name"], "arguments": json.dumps(f.get("arguments", {}))}})
                last_ids = [x["id"] for x in calls]
                msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": calls})
            elif m["role"] == "tool":
                msgs.append({"role": "tool", "tool_call_id": last_ids.pop(0) if last_ids else "call_0",
                             "content": m["content"]})
            else:
                msgs.append({"role": m["role"], "content": m["content"]})
        body = {"model": c.name, "messages": msgs, "temperature": c.temperature, "top_p": c.top_p,
                "seed": c.seed, "max_tokens": c.num_predict,
                "chat_template_kwargs": {"enable_thinking": overrides.pop("think", c.think)}}
        if tools:
            body["tools"] = tools
        req = urllib.request.Request(f"{c.host}/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer EMPTY"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=3600) as r:
            out = json.loads(r.read())
        wall = time.time() - t0
        msg = out["choices"][0]["message"]
        calls = []
        for tc in msg.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = tc["function"].get("arguments")
            calls.append({"id": tc.get("id"), "function": {"name": tc["function"]["name"], "arguments": args}})
        u = out.get("usage", {})
        ct = u.get("completion_tokens", 0)
        return ChatResult(content=msg.get("content") or "", tool_calls=calls,
                          thinking=msg.get("reasoning_content") or "",
                          prompt_tokens=u.get("prompt_tokens", 0), completion_tokens=ct,
                          wall_s=wall, gen_tok_per_s=ct / wall if wall else 0.0)


def make_llm(cfg: ModelConfig | None = None) -> LLM:
    cfg = cfg or ModelConfig.load()
    if cfg.backend == "ollama":
        return OllamaLLM(cfg)
    if cfg.backend == "openai":
        return OpenAICompatLLM(cfg)
    raise ValueError(f"unknown backend {cfg.backend!r}")
