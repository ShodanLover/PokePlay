"""Decode the Generation 3 (FireRed/LeafGreen, English) text encoding."""

from __future__ import annotations

_TABLE: dict[int, str] = {0x00: " "}
for i, ch in enumerate("0123456789"):
    _TABLE[0xA1 + i] = ch
for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _TABLE[0xBB + i] = ch
for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _TABLE[0xD5 + i] = ch
_TABLE.update({
    0x1B: "é", 0x2D: "&", 0x34: "Lv", 0x35: "=", 0x36: ";", 0x51: "¿", 0x52: "¡",
    0x53: "PK", 0x54: "MN", 0x5A: "Í", 0x5B: "%", 0x5C: "(", 0x5D: ")",
    0xAB: "!", 0xAC: "?", 0xAD: ".", 0xAE: "-", 0xAF: "·", 0xB0: "...",
    0xB1: '"', 0xB2: '"', 0xB3: "'", 0xB4: "'", 0xB5: "♂", 0xB6: "♀", 0xB7: "$",
    0xB8: ",", 0xB9: "x", 0xBA: "/", 0xEF: ">", 0xF0: ":",
    0xFA: " ", 0xFB: " ", 0xFE: " ",
})

# Number of argument bytes following an 0xFC control code.
_FC_ARGS = {
    0x01: 1, 0x02: 1, 0x03: 1, 0x04: 3, 0x05: 1, 0x06: 1, 0x07: 0, 0x08: 1,
    0x09: 0, 0x0A: 0, 0x0B: 2, 0x0C: 1, 0x0D: 1, 0x0E: 1, 0x0F: 0, 0x10: 2,
    0x11: 1, 0x12: 1, 0x13: 1, 0x14: 1, 0x15: 0, 0x16: 0, 0x17: 0, 0x18: 0,
}


def decode(data: bytes) -> str:
    out: list[str] = []
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0xFF:
            break
        if b == 0xFC and i + 1 < len(data):
            i += 2 + _FC_ARGS.get(data[i + 1], 0)
            continue
        if b == 0xFD:  # placeholder like the player's name
            i += 2
            continue
        out.append(_TABLE.get(b, ""))
        i += 1
    return " ".join("".join(out).split())


def encode_simple(text: str) -> bytes:
    """Reverse mapping for tests (letters, digits, space, basic punctuation)."""
    rev = {v: k for k, v in _TABLE.items() if len(v) == 1 and k not in (0xFA, 0xFB, 0xFE, 0xB2, 0xB4)}
    return bytes(rev[c] for c in text) + b"\xff"
