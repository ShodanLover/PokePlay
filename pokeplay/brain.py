"""The AI 'brain': asks a local model (via Ollama) what to do and what to say."""

from __future__ import annotations

import json
import random
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string"},
        "say": {"type": "string"},
        "choice": {"type": "integer"},
        "note": {"type": "string"},
    },
    "required": ["thought", "say", "choice"],
}


@dataclass
class Decision:
    thought: str
    say: str
    choice: int          # 0-based index into the options
    note: str = ""
    fallback: bool = False


class Brain:
    def __init__(self, url: str, model: str, streamer_name: str, temperature: float = 0.7,
                 context_tokens: int = 4096, timeout: float = 120.0):
        self.url = url.rstrip("/")
        self.model = model
        self.name = streamer_name
        self.temperature = temperature
        self.context_tokens = context_tokens
        self.timeout = timeout
        self._send_think = True

    # ------------------------------------------------------------------ transport
    def _chat(self, messages: list[dict], fmt=None, max_tokens: int = 300) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "60m",
            "options": {"temperature": self.temperature, "num_ctx": self.context_tokens,
                        "num_predict": max_tokens},
        }
        if fmt is not None:
            body["format"] = fmt
        if self._send_think:
            body["think"] = False      # skip slow hidden reasoning on models like Qwen3
        req = urllib.request.Request(f"{self.url}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if self._send_think and "think" in detail.lower():
                self._send_think = False
                return self._chat(messages, fmt, max_tokens)
            raise RuntimeError(f"Ollama error {e.code}: {detail}") from e
        return data.get("message", {}).get("content", "")

    def check(self) -> None:
        """Fail early with a helpful message if Ollama or the model isn't available."""
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=10) as resp:
                tags = json.loads(resp.read())
        except OSError as e:
            raise RuntimeError(f"Can't reach Ollama at {self.url}. Is Ollama running? ({e})") from e
        names = {m.get("name", "") for m in tags.get("models", [])}
        if self.model not in names and f"{self.model}:latest" not in names:
            raise RuntimeError(f"Model '{self.model}' isn't downloaded. Run:  ollama pull {self.model}")

    # ------------------------------------------------------------------ prompts
    def _system(self) -> str:
        return (
            f"You are {self.name}, an AI playing Pokémon FireRed live on a Twitch stream. "
            "You control the game by choosing from a numbered list of actions. "
            "You think out loud for your viewers: be upbeat, curious and a little funny, never rude. "
            "Choose the action that best moves you toward the current objective. "
            "Don't repeat actions that failed or that you've already picked many times in the same place; "
            "try something new instead. Unknown doorways are worth exploring."
        )

    def decide(self, context: str, option_lines: list[str]) -> Decision:
        numbered = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(option_lines))
        prompt = (
            f"{context}\n\nACTIONS YOU CAN TAKE:\n{numbered}\n\n"
            "Reply with JSON only: "
            '{"thought": "your reasoning, 1-2 sentences", '
            '"say": "one short, lively sentence to say out loud to chat", '
            '"choice": <action number>, '
            '"note": "optional: a short fact worth remembering long-term, or empty"}'
        )
        messages = [{"role": "system", "content": self._system()}, {"role": "user", "content": prompt}]
        try:
            raw = self._chat(messages, fmt=DECISION_SCHEMA, max_tokens=250)
            data = json.loads(_extract_json(raw))
            choice = int(data.get("choice", 1)) - 1
            if not 0 <= choice < len(option_lines):
                raise ValueError(f"choice {choice + 1} out of range")
            return Decision(str(data.get("thought", "")).strip(), str(data.get("say", "")).strip(), choice,
                            str(data.get("note", "") or "").strip())
        except Exception as e:  # noqa: BLE001 - never let the brain crash the stream
            print(f"[brain] decision failed ({e}); picking at random")
            choice = random.randrange(len(option_lines))
            return Decision("I couldn't make up my mind, so I'm going with my gut.",
                            "Let's try this way!", choice, fallback=True)

    def comment(self, events: list[str], context: str) -> str:
        prompt = (
            f"{context}\n\nWHAT JUST HAPPENED:\n" + "\n".join(f"- {e}" for e in events) +
            "\n\nReact out loud to your viewers in ONE short sentence (under 25 words). "
            "No emojis, no hashtags, no quotation marks."
        )
        messages = [{"role": "system", "content": self._system()}, {"role": "user", "content": prompt}]
        try:
            text = self._chat(messages, max_tokens=80)
        except Exception as e:  # noqa: BLE001
            print(f"[brain] comment failed: {e}")
            return ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip().strip('"')
        return text.split("\n")[0][:300]


def _extract_json(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON in reply: {text[:120]!r}")
    return text[start:end + 1]
