# Copyright (c) 2026 funmaker
# SPDX-License-Identifier: MIT

"""Pure collection/field helpers for the Copy Known Words addon."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from anki.collection import Collection
from anki.decks import DeckId

_WHITESPACE = re.compile(r"\s+")
_SOUND_TAG = re.compile(r"\[sound:[^\]]*\]", re.IGNORECASE)


class _TextExtractor(HTMLParser):
    """Turn an Anki field's HTML into a single line of plain text."""

    _BLOCK_TAGS = {"br", "div", "p", "li", "tr", "td", "th"}
    _SKIP_TAGS = {"rt", "rp", "style", "script"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._BLOCK_TAGS:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self._BLOCK_TAGS:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def field_to_word(field: str) -> str:
    """Convert the raw contents of a note field to one clean line."""
    parser = _TextExtractor()
    try:
        parser.feed(field or "")
        parser.close()
    except Exception:
        # A malformed field should never stop the whole export.
        return ""
    text = _SOUND_TAG.sub(" ", parser.text())
    return _WHITESPACE.sub(" ", text).strip()


def known_words(
    col: Collection, deck_id: DeckId, only_reviewed: bool = True
) -> list[str]:
    """Return unique first-field words, oldest card first.

    Subdecks are included, matching how Anki studies a deck.  When
    ``only_reviewed`` is true, cards that have never been reviewed
    (``reps == 0``) and cards still in the new state are skipped.
    """
    deck_ids = col.decks.deck_and_child_ids(deck_id)
    if not deck_ids:
        return []

    placeholders = ",".join("?" for _ in deck_ids)
    conditions = [f"did in ({placeholders})"]
    if only_reviewed:
        conditions.extend(["reps > 0", "type != 0"])
    card_ids = col.db.list(
        f"select id from cards "
        f"where {' and '.join(conditions)} "
        f"order by id asc",
        *deck_ids,
    )

    words: list[str] = []
    seen: set[str] = set()
    for card_id in card_ids:
        card = col.get_card(card_id)
        note = card.note()
        if not note.fields:
            continue
        word = field_to_word(note.fields[0])
        if word and word not in seen:
            seen.add(word)
            words.append(word)
    return words
