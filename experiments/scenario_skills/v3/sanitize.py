"""Privacy scan: v3 fixtures must be synthetic and share nothing identifying with the evidence packet.

Rejects a fixture string that
- shares any run of 8 consecutive words with a packet transcript, tool result or metric explanation;
- contains an email address or a phone number outside the fictional 555 range;
- contains a proper name (capitalized word sequence) that also appears in the packet.

The report names fixture locations only; packet text is never printed or written.

    python3 -m experiments.scenario_skills.v3.sanitize <packet-dir>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORD = re.compile(r"[a-z0-9']+")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
PROPER = re.compile(r"\b[A-Z][a-z]+(?:[ -][A-Z][a-z]+)+\b")
# Capitalized phrases that are ordinary product or English vocabulary, not identifying names.
COMMON = {"Expected Outcome", "Infrastructure Issues", "Tool Call Success", "Response Relevancy", "Caller Sentiment",
          "Interruption Handling", "Voice Clarity", "Normal Male", "Normal Female", "Normal Spanish", "Normal German",
          "Interruptive High", "Slow Speaker", "Call Flow", "Card Services", "Main Agent", "Testing Agent", "Live Lookup",
          "Legacy Shared", "Happy Path", "Edge Case", "New Patient", "Mandatory Disclosure", "Call Start", "Payment Plan"}
# Keypad-entered fictional identifiers that are digit strings by design, not phone numbers.
DIGIT_IDENTIFIERS = ("tracking_number",)
N = 8


def strings(value, path="$"):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from strings(v, "%s.%s" % (path, k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from strings(v, "%s[%d]" % (path, i))
    elif isinstance(value, str):
        yield path, value


def shingles(text):
    words = WORD.findall(text.lower())
    return {" ".join(words[i:i + N]) for i in range(len(words) - N + 1)}


def packet_text(directory):
    for path in sorted((Path(directory) / "calls").glob("*.json")):
        record = json.loads(path.read_text())
        for _, text in strings({"t": record.get("transcript_object"), "e": record.get("evaluation"), "m": record.get("metrics")}):
            yield text


def fixture_values(root):
    for name in ("packs.json", "expectations.json", "judge-gold.json"):
        path = root / name
        if path.exists():
            yield name, json.loads(path.read_text())


def scan(directory, root=Path(__file__).parent / "fixtures"):
    packet_shingles, packet_blob = set(), []
    for text in packet_text(directory):
        packet_shingles |= shingles(text)
        packet_blob.append(text)
    blob = "\n".join(packet_blob)
    findings, names, checked = [], {}, 0
    for name, value in fixture_values(root):
        for path, text in strings(value):
            checked += 1
            if shingles(text) & packet_shingles:
                findings.append({"file": name, "path": path, "reason": "8-word overlap with packet"})
            if EMAIL.search(text):
                findings.append({"file": name, "path": path, "reason": "email address"})
            for number in ([] if path.endswith(DIGIT_IDENTIFIERS) else PHONE.findall(text)):
                digits = re.sub(r"\D", "", number)
                if len(digits) >= 10 and "555" not in digits[:5]:
                    findings.append({"file": name, "path": path, "reason": "phone number outside the 555 range"})
            for proper in PROPER.findall(text):
                if proper not in COMMON:
                    names.setdefault(proper, (name, path))
    for proper, (name, path) in sorted(names.items()):
        if re.search(r"\b%s\b" % re.escape(proper), blob):
            findings.append({"file": name, "path": path, "reason": "proper name also present in packet"})
    return {"strings_checked": checked, "packet_files": len(packet_blob) and len(list((Path(directory) / "calls").glob("*.json"))),
            "proper_names_checked": len(names), "findings": findings, "clean": not findings}


if __name__ == "__main__":
    report = scan(sys.argv[1])
    print(json.dumps({k: v for k, v in report.items() if k != "findings"} | {"findings": report["findings"][:50]}, indent=1))
    sys.exit(0 if report["clean"] else 1)
