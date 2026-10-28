"""Share repeated long strings without removing training observations.

Tool arguments/results, candidate bodies and final states remain reconstructable
exactly. This is a transport representation, not summarization or task selection.
"""
from collections import Counter
import hashlib

REFERENCE = "$shared_training_text"


def encode(value, minimum_chars=256):
    counts = Counter()

    def visit(node):
        if isinstance(node, str) and len(node) >= minimum_chars:
            counts[node] += 1
        elif isinstance(node, dict):
            if REFERENCE in node:
                raise ValueError("Training data collides with transport reference marker")
            for item in node.values():
                visit(item)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(value)
    identifiers = {text: hashlib.sha256(text.encode()).hexdigest()
                   for text, count in counts.items() if count > 1}

    def replace(node):
        if isinstance(node, str) and node in identifiers:
            return {REFERENCE: identifiers[node]}
        if isinstance(node, dict):
            return {key: replace(item) for key, item in node.items()}
        if isinstance(node, list):
            return [replace(item) for item in node]
        return node

    packet = {"format": "shared-training-text-v1",
              "shared_text": {identifier: text for text, identifier in identifiers.items()},
              "records": replace(value)}
    if decode(packet) != value:
        raise ValueError("Training transport failed its lossless round trip")
    return packet


def decode(packet):
    if packet.get("format") != "shared-training-text-v1":
        raise ValueError("Unknown training transport format")
    texts = packet["shared_text"]
    for identifier, text in texts.items():
        if hashlib.sha256(text.encode()).hexdigest() != identifier:
            raise ValueError("Shared training text hash does not match")

    def restore(node):
        if isinstance(node, dict):
            if set(node) == {REFERENCE}:
                return texts[node[REFERENCE]]
            return {key: restore(item) for key, item in node.items()}
        if isinstance(node, list):
            return [restore(item) for item in node]
        return node

    return restore(packet["records"])
