"""The AI 'brain': asks a local model (via Ollama) what to do and what to say."""

from __future__ import annotations

import json
import random
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

# The only fixed rules: safeguards for a public Twitch stream.
SAFETY = (
    "Rules you must always follow: keep it family-friendly and within Twitch's community guidelines; "
    "no slurs, hate, harassment, sexual content or graphic violence; don't talk about real people's "
    "private lives; never pretend to be a real person. "
)

# She knows nothing about Pokémon except what she has learned on stream.
FIRST_TIMER = (
    "You have NEVER played or seen any Pokémon game, show or card, and you know nothing about it: not the "
    "creatures, their types, the places, the people or the story. Everything you know comes from what you "
    "have seen and been told on this stream, which is in your journal. If you catch yourself 'remembering' "
    "a Pokémon fact you didn't learn here, ignore it or treat it as a wild guess. Figure the game out by "
    "trying things, reading what people say, and learning from what happens. "
)


class BrainOffline(RuntimeError):
    """Ollama can't be reached; the agent waits and retries instead of acting blindly."""


DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string"},
        "say": {"type": "string"},
        "choice": {"type": "integer"},
        "note": {"type": "string"},
        "goal": {"type": "string"},
    },
    "required": ["thought", "say", "choice"],
}


@dataclass
class Decision:
    thought: str
    say: str
    choice: int          # 0-based index into the options
    note: str = ""
    goal: str = ""
    fallback: bool = False


class Brain:
    def __init__(self, url: str, model: str, streamer_name: str = "", temperature: float = 0.7,
                 context_tokens: int = 4096, timeout: float = 120.0, personality: str = ""):
        self.url = url.rstrip("/")
        self.model = model
        self.name = streamer_name or "the streamer"
        self.personality = personality
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
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            raise BrainOffline(f"Ollama unreachable: {e}") from e
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
            + (f"Your personality: {self.personality} " if self.personality else "")
            + "You are fully in control of the game; you choose from a numbered list of actions. "
            + FIRST_TIMER
            + "You set your own goals. You think out loud for your viewers, in first person, fully in "
            "your own voice and personality. "
            + SAFETY
        )

    def decide(self, context: str, option_lines: list[str]) -> Decision:
        numbered = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(option_lines))
        prompt = (
            f"{context}\n\nACTIONS YOU CAN TAKE:\n{numbered}\n\n"
            "Reply with JSON only: "
            '{"thought": "your reasoning, 1-2 sentences", '
            '"say": "think out loud to chat in 1-3 short spoken sentences: what you notice and why you chose this", '
            '"choice": <action number>, '
            '"note": "optional: something you learned that is worth writing in your journal, or empty", '
            '"goal": "optional: your new goal if you want to change it, or empty"}'
        )
        messages = [{"role": "system", "content": self._system()}, {"role": "user", "content": prompt}]
        try:
            raw = self._chat(messages, fmt=DECISION_SCHEMA, max_tokens=400)
            data = json.loads(_extract_json(raw))
            choice = int(data.get("choice", 1)) - 1
            if not 0 <= choice < len(option_lines):
                raise ValueError(f"choice {choice + 1} out of range")
            return Decision(str(data.get("thought", "")).strip(), str(data.get("say", "")).strip(), choice,
                            str(data.get("note", "") or "").strip(), str(data.get("goal", "") or "").strip())
        except BrainOffline:
            raise
        except Exception as e:  # noqa: BLE001 - never let the brain crash the stream
            print(f"[brain] decision failed ({e}); picking at random")
            choice = random.randrange(len(option_lines))
            return Decision("", "", choice, fallback=True)   # stay quiet rather than fake a thought

    def create_persona(self, hint: str) -> dict:
        """Let the AI invent its own streamer identity."""
        schema = {"type": "object",
                  "properties": {"name": {"type": "string"}, "personality": {"type": "string"},
                                 "catchphrase": {"type": "string"}},
                  "required": ["name", "personality", "catchphrase"]}
        prompt = (
            f"You are an AI about to start your very own Twitch channel where you play Pokémon FireRed "
            f"and think out loud. You are {hint}. Everything else about you is your choice. "
            "Choose your own streamer name (easy to say out loud, not a real person's name and not a "
            "Pokémon character's name), describe your own personality in one sentence, and pick a catchphrase. "
            'Reply with JSON: {"name": "...", "personality": "...", "catchphrase": "..."}'
        )
        for _ in range(3):
            try:
                data = json.loads(_extract_json(self._chat([{"role": "user", "content": prompt}],
                                                           fmt=schema, max_tokens=150)))
                name = " ".join(str(data.get("name", "")).split())[:24]
                if name:
                    return {"name": name, "personality": str(data.get("personality", "")).strip(),
                            "catchphrase": str(data.get("catchphrase", "")).strip()}
            except Exception as e:  # noqa: BLE001
                print(f"[brain] persona attempt failed: {e}")
        raise RuntimeError("The AI couldn't come up with a name. Is Ollama working? Try again.")

    def choose_name(self, kind: str, max_chars: int, species: str = "", context: str = "") -> tuple[str, str]:
        """Pick an in-game name. Returns (name, what to say about it)."""
        what = {
            "player": "your own trainer character",
            "rival": "the rival the game just introduced",
            "nickname": f"your new {species}",
            "caught": f"the {species} you just caught",
            "box": "a PC storage box",
        }.get(kind, "this")
        schema = {"type": "object", "properties": {"name": {"type": "string"}, "say": {"type": "string"}},
                  "required": ["name", "say"]}
        prompt = (
            (context + "\n\n" if context else "")
            + f"You get to type a name for {what}. It must be at most {max_chars} characters, "
            "using only English letters, digits, spaces and . , ! ? - ' "
            + ("You might want to use your own name or a short version of it. " if kind == "player" else "")
            + 'Reply with JSON: {"name": "...", "say": "one or two sentences out loud about why you picked it"}'
        )
        messages = [{"role": "system", "content": self._system()}, {"role": "user", "content": prompt}]
        try:
            data = json.loads(_extract_json(self._chat(messages, fmt=schema, max_tokens=120)))
            return str(data.get("name", "")).strip(), str(data.get("say", "")).strip()
        except Exception as e:  # noqa: BLE001
            print(f"[brain] naming failed: {e}")
            return "", ""

    def reflect(self, context: str) -> dict:
        """Step back: update her goal and mood, maybe write a journal entry."""
        schema = {"type": "object",
                  "properties": {"goal": {"type": "string"}, "mood": {"type": "string"},
                                 "journal": {"type": "string"}},
                  "required": ["goal", "mood"]}
        prompt = (
            f"{context}\n\nTake a moment to reflect, privately. Based only on what you've experienced, "
            "what is your goal right now? How do you feel (one or two words)? Is there anything new worth "
            'writing in your journal? Reply with JSON: {"goal": "...", "mood": "...", "journal": "... or empty"}'
        )
        messages = [{"role": "system", "content": self._system()}, {"role": "user", "content": prompt}]
        try:
            data = json.loads(_extract_json(self._chat(messages, fmt=schema, max_tokens=200)))
            return {k: str(data.get(k, "") or "").strip() for k in ("goal", "mood", "journal")}
        except BrainOffline:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"[brain] reflect failed: {e}")
            return {}

    def condense(self, entries: list[str], keep: int = 15) -> list[str]:
        """Shrink a long journal into its most important points (keeps memory small)."""
        schema = {"type": "object", "properties": {"entries": {"type": "array", "items": {"type": "string"}}},
                  "required": ["entries"]}
        prompt = (
            "Here is your journal from playing this game:\n" + "\n".join(f"- {e}" for e in entries) +
            f"\n\nRewrite it as at most {keep} short entries, keeping everything important you learned "
            "(people, places, how things work, your plans, your feelings about your team). "
            'Reply with JSON: {"entries": ["...", "..."]}'
        )
        try:
            data = json.loads(_extract_json(self._chat([{"role": "user", "content": prompt}], fmt=schema,
                                                       max_tokens=900)))
            out = [str(e).strip() for e in data.get("entries", []) if str(e).strip()]
            return out[:keep] if out else entries
        except BrainOffline:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"[brain] condense failed: {e}")
            return entries[-keep:]

    def greet(self, context: str = "") -> str:
        """Her own opening line for the stream."""
        return self.comment(["The stream just started and viewers are arriving. Say hello however you like."], context)

    def comment(self, events: list[str], context: str) -> str:
        prompt = (
            f"{context}\n\nWHAT JUST HAPPENED:\n" + "\n".join(f"- {e}" for e in events) +
            "\n\nReact out loud to your viewers in one or two short spoken sentences (under 35 words total). "
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
