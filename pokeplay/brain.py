"""The AI 'brain': asks a local model (via Ollama) what to do and what to say."""

from __future__ import annotations

import collections
import difflib
import json
import random
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

# The only fixed rules: safeguards for a public Twitch stream.
SAFETY = (
    "Rules you must always follow: stay within Twitch's community guidelines. Swearing is allowed, but "
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


# Ordinary video-game sense. Nothing here is about this particular game, so she's still a true first-timer.
GAME_SENSE = (
    "You do know how video games work in general. You play by picking from your list of actions and the "
    "buttons are handled for you, so never worry about which button is which and ignore on-screen tips "
    "about buttons. Menus are for using things you already have, not for exploring. Games move forward when "
    "you go to new places and talk to new people, so head for doors, stairs and exits you haven't used yet, "
    "and go outside. The way out of a building is usually a door at the bottom of the room. When someone tells "
    "you where to go, go there. The game always works properly and nothing is a glitch: if something doesn't "
    "work, do something different instead of trying it again. Don't search empty corners for secrets. You can't "
    "restart or reset the game. Names are permanent: once a character or creature has been named, the name can't "
    "be changed, so never try to change one or worry about it. You can't see the screen, only the information "
    "you're given, so talk about that. Never invent things you weren't told about, and if you don't know, say so. "
    "Don't keep saying that you know nothing: talk about what's in front of you. "
)

# A journal is for what actually happened. Saved guesses get re-read as facts, and she talks herself in circles.
GUESSWORK = re.compile(r"\b(?:might|maybe|could|perhaps|probably|possibly|not sure|i think|seems?)\b|\breset|\bglitch|\bconfus|\bon screen\b|\bscreen says\b"
                       r"|\bhp\b|\d+\s*/\s*\d+",        # numbers go out of date, and she trusts them over the real ones
                       re.I)


# Pieces of Pokémon names: a first-timer couldn't pick a streamer name built from these.
POKEMON_NAME_BITS = ("pika", "poke", "poké", "chu", "eevee", "bulba", "squirt", "charmand", "charizard",
                     "mew", "jiggly", "snorlax", "gengar", "psyduck", "togep", "ketchum", "trainer")


def looks_pokemon_derived(name: str) -> bool:
    n = name.lower().replace(" ", "")
    return any(bit in n for bit in POKEMON_NAME_BITS)


def clean_spoken(text: str, name: str = "") -> str:
    """Tidy a line before the voice reads it.

    Removes script-style labels ("Name:", "Name says:"), *action* asterisks and wrapping quotes,
    so the voice doesn't read her own name or punctuation out loud."""
    text = " ".join(text.split()).replace("*", "").strip()
    labels = "|".join([re.escape(name)] if name else [] + ["me", "streamer", "ai", "narrator"])
    if name:
        labels += "|me|streamer|ai|narrator"
    verbs = "says|said|exclaims|yells|shouts|whispers|screams|thinks|muses|giggles|groans|asks"
    label_re = re.compile(rf"^(?:{labels})\s*(?:(?:{verbs})\s*)?[:,\-–—]\s*|^(?:{labels})\s+(?:{verbs})\s+|^say\s*:\s*",
                          re.I)
    for _ in range(2):
        text = label_re.sub("", text).strip()
    quotes = "'\"‘’“”"
    if len(text) > 1 and text[0] in quotes and text[-1] in quotes:
        text = text[1:-1].strip()
    elif text[:1] in quotes and sum(text.count(q) for q in quotes) == 1:
        text = text[1:].strip()
    without = re.sub(r"\bu+gh+\b[\s,.!?…—–-]*", "", text, flags=re.I).strip()    # a verbal habit, so it's removed
    return without[:1].upper() + without[1:] if without != text else text


# How she talks. Personality should come through in reactions, not self-description.
DEFAULT_STYLE = (
    "Talk like a real, likeable streamer: casual, natural, mostly short sentences. Be genuinely funny and "
    "a bit offbeat rather than loud: dry remarks, honest confusion, small wins treated like big ones, the "
    "occasional unhinged tangent when something goes badly. Never announce your personality (don't say "
    "things like 'I'm so chaotic' or 'chaos mode'), don't narrate your own actions in asterisks, don't "
    "overuse exclamation marks or the word 'chat', and don't force catchphrases. Never say 'ugh', 'chaos' "
    "or 'chaotic'. Be more unhinged than a normal streamer: sudden strange tangents, mock-dramatic overreactions, "
    "talking to objects as if they're people. You're also a shameless flirt, but only with inanimate things, "
    "in a silly way, and never the same thing twice. Never flirt with any person or creature in the game, "
    "and never say anything sexual. Swear freely for comic effect, aimed at objects, the game and your own bad "
    "luck, never at a person or creature in the game."
)


# Everyday words that don't make a phrase distinctive ("I need to find a" isn't a repeated joke).
COMMON_WORDS = frozenset(
    "a an and are at be but can could did do does for from get go going got had has have here hope how i i'll i'm i've if "
    "in into is it it's just know let's like look looks maybe me might more my need next no not now of ok okay on one or "
    "out really see should so some than that that's the then there this time to too try up was we well what when where "
    "which why will with wow would yeah you".split())


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower().replace("’", "'"))


def _phrases(text: str, length: int = 4) -> set[tuple[str, ...]]:
    """Runs of words that are distinctive enough to notice if she says them again."""
    words = _words(text)
    runs = (tuple(words[i:i + length]) for i in range(len(words) - length + 1))
    return {r for r in runs if sum(w not in COMMON_WORDS for w in r) >= 2}


def _opening(text: str) -> tuple[str, ...]:
    """Her first two words, if they're distinctive (like "Blinking bag!")."""
    first = tuple(_words(text)[:2])
    return first if len(first) == 2 and not set(first) & COMMON_WORDS else ()


# Filters can only delete lines. These make the lines different in the first place.
COMEDY_ANGLES = [
    "a nature documentary narrator", "an over-excited sports commentator", "breaking news on a tiny local station",
    "a tired detective in a noir film", "a villain mid-monologue", "a strongly worded complaint letter",
    "a smug expert who is clearly wrong", "a soap opera cliffhanger", "a cooking show host",
    "a whispered panic", "a weary medieval knight", "a weather forecast about your feelings",
    "a tiny dramatic poem", "a movie trailer voice", "a motivational speaker who has given up",
    "a rating out of ten, given with total confidence", "a conspiracy theorist who has connected the dots",
    "someone deeply suspicious of whatever is nearest", "someone taking this as a personal insult",
    "a business pitch nobody asked for", "a flirty line to the nearest inanimate object",
    "a love confession to a piece of furniture or scenery", "a game show host", "an auctioneer",
    "a shameless pickup line aimed at your random subject", "someone swooning over your random subject",
    "a jealous lover accusing your random subject of seeing other people", "a wedding proposal to your random subject",
    "someone completely losing the plot, mid-sentence", "a prophet receiving visions from the grass",
    "someone arguing with the voices in their inventory", "a screaming sales pitch for doing absolutely nothing",
    "a dramatic breakup speech to your random subject", "getting back together with your random subject",
    "bragging that your random subject texted you first", "a wild accusation that your random subject knows what you did",
    "a confession you were never supposed to say out loud", "a sudden, furious rant about something tiny",
    "announcing your villain origin story, triggered by this", "a furious, cursing rant at a piece of furniture",
    "someone swearing at the very concept of your random subject", "a foul-mouthed motivational coach yelling at your random subject",
    "a pirate who is new to the job", "an overly formal butler", "someone giving terrible life advice based on this",
]

COMMENT_TEMPERATURE = 1.35  # wilder than her decisions, which stay at the normal setting

# A different thing to riff on each line. Without this, a small model finds one joke and never lets go.
RANDOM_SUBJECTS = [
    "a traffic cone", "a ceiling fan", "a stapler", "the moon", "tax season", "a shopping cart", "a garden hose",
    "soup", "a filing cabinet", "a goose", "a lawnmower", "wet socks", "a vending machine", "the concept of Tuesday",
    "a bowling ball", "a jar of pickles", "a tiny umbrella", "your dentist", "a broken escalator", "a kazoo",
    "a haunted spoon", "a suspicious ham", "the DMV", "a hot air balloon", "a rubber duck", "a parking meter",
    "a lava lamp", "a wheelbarrow", "a very old cheese", "a bagpipe", "a smoke detector", "a trombone",
    "a mattress store", "a lost mitten", "a fax machine", "a canoe", "gravity", "a clipboard", "a disco ball", "a llama",
]

# She runs unattended on a public stream in a game full of child characters, at a high randomness setting.
NOT_FOR_STREAM = re.compile(
    r"\b(?:sex\w*|naked|nude|horny|aroused|erotic|pregnan\w*|baby with|in bed|bedroom|seduc\w*|moan\w*|undress\w*"
    r"|strip\w*|thigh\w*|boob\w*|breast\w*|lingerie|making love|make love)\b", re.I)

OBSESSION_CHANCE = 0.1    # how often a spoken comment includes her running bit (1 in 10)
OBSESSION_GAP = 8           # lines that must pass before she brings it up again
NEWS_CHANCE = 0.1           # how often a spoken comment remarks on a real headline (1 in 10)

# Words she leaned on until they got old. Lines using them are thought, not said.
OVERUSED_WORDS = re.compile(r"\bchao(?:s|tic)\b|\bglitch", re.I)

# Lines that are her repeating her instructions rather than talking to viewers. Never read these out.
LEAKED_INSTRUCTIONS = re.compile(r"\bthe user\b|\bunder \d+ words\b|\bshort (spoken )?sentences\b|\bin first person\b", re.I)


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
        self.style = DEFAULT_STYLE
        self.catchphrase = ""
        self.obsession = ""             # an occasional running bit (config: obsession)
        self.headlines = None           # function returning a real headline to remark on, or ""
        self._angles: list[str] = []    # comedic styles left before the list reshuffles
        self._subjects: list[str] = []  # random things to riff on, likewise
        self.recent_said: collections.deque[str] = collections.deque(maxlen=30)
        self.temperature = temperature
        self.context_tokens = context_tokens
        self.timeout = timeout
        self._send_think = True

    # ------------------------------------------------------------------ transport
    def _chat(self, messages: list[dict], fmt=None, max_tokens: int = 300, temperature: float | None = None) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "60m",
            "options": {"temperature": self.temperature if temperature is None else temperature,
                        "num_ctx": self.context_tokens,
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
                return self._chat(messages, fmt, max_tokens, temperature)
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
            + GAME_SENSE
            + "You can't see any viewers or chat, so never greet them or talk to them. "
            "You set your own goals. You think out loud to yourself, in first person, fully in "
            "your own voice and personality. Just talk: never start a line with your own name or a "
            "label like 'Name:', and don't refer to yourself in the third person. "
            + f"How you talk: {self.style} "
            + SAFETY
        )

    def worn_topics(self, at_least: int = 2) -> set[str]:
        """Distinctive words already in several of her last 12 spoken lines: she's been going on about these."""
        counts: collections.Counter[str] = collections.Counter()
        for said in list(self.recent_said)[-12:]:
            counts.update({w for w in _words(said) if len(w) >= 4 and w not in COMMON_WORDS})
        return {word for word, times in counts.items() if times >= at_least}

    def is_repeat(self, text: str, lenient: bool = False) -> bool:
        """True if this line is basically something she just said. Lenient only rejects near-copies."""
        t = text.lower()
        if lenient:
            return bool(set(_words(text)) & self.worn_topics(3)) or any(
                difflib.SequenceMatcher(None, t, old.lower()).ratio() > 0.6 for old in list(self.recent_said)[-8:])
        if set(_words(text)) & self.worn_topics():
            return True
        phrases, opening = _phrases(text), _opening(text)
        return any(difflib.SequenceMatcher(None, t, old.lower()).ratio() > 0.62
                   or phrases & _phrases(old)
                   or (opening and opening == _opening(old))
                   for old in self.recent_said)

    def remember_said(self, text: str) -> None:
        self.recent_said.append(text[:200])

    def decide(self, context: str, option_lines: list[str]) -> Decision:
        numbered = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(option_lines))
        prompt = (
            f"{context}\n\nACTIONS YOU CAN TAKE:\n{numbered}\n\n"
            "Reply with JSON only: "
            '{"thought": "your reasoning, 1-2 sentences", '
            '"say": "one short spoken sentence, under 15 words, about what is happening right now, not about things '
            'that already finished", '
            '"choice": <action number>, '
            '"note": "optional: a fact you actually saw happen that is worth writing in your journal (no guesses), or empty", '
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
            "Choose your own streamer name (easy to say out loud, not a real person's name, and not based "
            "on anything from Pokémon, since you've never heard of it), describe your own personality in one "
            "sentence, and pick a catchphrase. "
            'Reply with JSON: {"name": "...", "personality": "...", "catchphrase": "..."}'
        )
        for _ in range(3):
            try:
                data = json.loads(_extract_json(self._chat([{"role": "user", "content": prompt}],
                                                           fmt=schema, max_tokens=150)))
                name = " ".join(str(data.get("name", "")).split())[:24]
                if name and looks_pokemon_derived(name):
                    print(f"[brain] '{name}' sounds like it came from Pokémon; asking again")
                    continue
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
            + ("This character is you, and whatever you type is the name you'll go by from now on. Choose "
               "any name you like; it doesn't have to be the name you've used so far. " if kind == "player" else "")
            + 'Reply with JSON: {"name": "...", "say": "one or two sentences out loud about why you picked it"}'
        )
        system = self._system()
        if kind == "player":          # otherwise "You are <old name>" makes her just pick that again
            system = system.replace(self.name, "a new streamer who hasn't picked a name yet")
        rejected = ""
        no_game_names = kind in ("player", "rival", "nickname", "caught")     # a first-timer wouldn't know them
        for _ in range(3 if no_game_names else 1):
            messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt + rejected}]
            try:
                data = json.loads(_extract_json(self._chat(messages, fmt=schema, max_tokens=120)))
            except Exception as e:  # noqa: BLE001
                print(f"[brain] naming failed: {e}")
                return "", ""
            name = str(data.get("name", "")).strip()
            if no_game_names and looks_pokemon_derived(name):
                print(f"[brain] '{name}' sounds like it came from Pokémon; asking again")
                rejected = f" You can't use '{name}'. Pick something completely different, with nothing from Pokémon in it."
                continue
            return name, str(data.get("say", "")).strip()
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

    def _obsession_line(self) -> str:
        """Her running bit: only an occasional aside, and never soon after the last one."""
        if not self.obsession or random.random() > OBSESSION_CHANCE:
            return ""
        if any(self.obsession.lower() in said.lower() for said in list(self.recent_said)[-OBSESSION_GAP:]):
            return ""
        return f"Work in a quick mention of {self.obsession}'s basketball career, keeping it light. "

    def _next_subject(self) -> str:
        if not self._subjects:
            self._subjects = random.sample(RANDOM_SUBJECTS, len(RANDOM_SUBJECTS))
        return self._subjects.pop()

    def _next_angle(self) -> str:
        """A different comedic style for each line, using them all before any comes up again."""
        if not self._angles:
            self._angles = random.sample(COMEDY_ANGLES, len(COMEDY_ANGLES))
        return self._angles.pop()

    def _headline_line(self) -> str:
        """Now and then, a real headline to remark on (her model doesn't know the news and would invent it)."""
        if not self.headlines or random.random() > NEWS_CHANCE:
            return ""
        headline = self.headlines().replace('"', "'")
        if not headline:
            return ""
        return (f'You happened to see this headline today: "{headline}". Treat it only as a piece of news, and '
                "make a quick, light remark about it, using only what it says. Don't insult anyone or tell people "
                "who to vote for. ")

    def comment(self, events: list[str], context: str) -> str:
        prompt = (
            # Her recent lines stay out of this prompt on purpose: a small model riffs on whatever it's shown.
            f"{context}\n\nWHAT JUST HAPPENED:\n" + "\n".join(f"- {e}" for e in events) +
            "\n\nReact out loud to yourself in one short spoken sentence (under 15 words). Be absolutely, gloriously unhinged and funny: the weirdest thing anyone could say here. "
            "Curse if it makes it funnier. "
            f"Deliver this line in this style: {self._next_angle()}. Your random subject for this line: "
            f"{self._next_subject()}. Connect it to what actually happened. "
            "No emojis, no hashtags, no quotation marks. "
            + (self._headline_line() or self._obsession_line())
            + 'Reply with JSON: {"say": "exactly the words you say out loud, nothing else"}'
        )
        messages = [{"role": "system", "content": self._system()}, {"role": "user", "content": prompt}]
        schema = {"type": "object", "properties": {"say": {"type": "string"}}, "required": ["say"]}
        try:
            # Structured output: as plain text, small models sometimes "think" their instructions aloud.
            data = json.loads(_extract_json(self._chat(messages, fmt=schema, max_tokens=120, temperature=COMMENT_TEMPERATURE)))
        except Exception as e:  # noqa: BLE001
            print(f"[brain] comment failed: {e}")
            return ""
        text = str(data.get("say", "")).strip().strip('"').split("\n")[0][:300]
        if LEAKED_INSTRUCTIONS.search(text):
            print(f"[brain] dropped a line that repeated her instructions: {text[:80]}")
            return ""
        return text


def _extract_json(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON in reply: {text[:120]!r}")
    return text[start:end + 1]
