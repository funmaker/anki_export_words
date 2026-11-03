# Copyright (c) 2026 funmaker
# SPDX-License-Identifier: MIT

"""Export words from a deck to the clipboard or a text file.

The addon adds three ways to open the same dialog:

* Tools -> "Export words..."
* the gear/options menu next to a deck in the deck browser
* right-clicking a deck in the Browser sidebar

The dialog lets you choose the deck and whether to include only reviewed
cards or all cards, then copy the result to the clipboard or save it to a
file.  Words are taken from the first field of each note, duplicates are
removed, and the list is ordered oldest card first.
"""

from __future__ import annotations

import re
from pathlib import Path

from anki.decks import DeckId
from aqt import gui_hooks, mw
from aqt.operations import QueryOp
from aqt.qt import (
    QAction,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
)
from aqt.utils import qconnect, showWarning, tooltip

from .logic import known_words

_SEPARATOR = ", "
_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _export_deck(
    deck_id: DeckId, only_reviewed: bool, destination: str | None
) -> None:
    """Export words to the clipboard when destination is None, else to a file."""
    if not mw.col:
        return

    def on_success(words: list[str]) -> None:
        if not words:
            tooltip("No matching cards found in this deck.", parent=mw)
            return

        text = _SEPARATOR.join(words)
        if destination is None:
            QApplication.clipboard().setText(text)
            tooltip(f"Copied {len(words)} words to the clipboard.", parent=mw)
            return

        try:
            Path(destination).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            showWarning(f"Could not save the file:\n{exc}", parent=mw)
            return
        tooltip(f"Saved {len(words)} words to {destination}.", parent=mw)

    QueryOp(
        parent=mw,
        op=lambda col: known_words(col, deck_id, only_reviewed),
        success=on_success,
    ).with_progress("Exporting words...").run_in_background()


def _ask_for_save_path(deck_name: str) -> str | None:
    safe_name = _INVALID_FILENAME_CHARS.sub("-", deck_name.replace("::", " - "))
    safe_name = safe_name.strip() or "words"
    default_path = Path.home() / f"{safe_name} words.txt"

    path, _ = QFileDialog.getSaveFileName(
        mw,
        "Save Words",
        str(default_path),
        "Text files (*.txt);;All files (*)",
    )
    if not path:
        return None
    if not Path(path).suffix:
        path += ".txt"
    return path


def _show_export_dialog(default_deck_id: DeckId) -> None:
    if not mw.col:
        return

    decks = list(mw.col.decks.all_names_and_ids())
    if not decks:
        tooltip("No decks found.", parent=mw)
        return

    dialog = QDialog(mw)
    dialog.setWindowTitle("Export Words")
    dialog.setMinimumWidth(420)

    layout = QVBoxLayout(dialog)
    form = QFormLayout()

    deck_combo = QComboBox()
    selected_index = 0
    for index, deck in enumerate(decks):
        deck_combo.addItem(deck.name, int(deck.id))
        if int(deck.id) == int(default_deck_id):
            selected_index = index
    deck_combo.setCurrentIndex(selected_index)
    form.addRow("Deck:", deck_combo)

    filter_combo = QComboBox()
    filter_combo.addItem("Only Reviewed", True)
    filter_combo.addItem("All", False)
    form.addRow("Cards:", filter_combo)

    layout.addLayout(form)

    chosen_action: dict[str, str | None] = {"value": None}

    def choose(action: str) -> None:
        chosen_action["value"] = action
        dialog.accept()

    cancel_button = QPushButton("Cancel")
    copy_button = QPushButton("Copy to Clipboard")
    save_button = QPushButton("Save to File")
    copy_button.setDefault(True)

    qconnect(cancel_button.clicked, dialog.reject)
    qconnect(copy_button.clicked, lambda: choose("copy"))
    qconnect(save_button.clicked, lambda: choose("save"))

    button_layout = QHBoxLayout()
    button_layout.addStretch()
    button_layout.addWidget(cancel_button)
    button_layout.addWidget(copy_button)
    button_layout.addWidget(save_button)
    layout.addLayout(button_layout)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    action = chosen_action["value"]
    if action is None:
        return

    deck_id = DeckId(deck_combo.currentData())
    only_reviewed = bool(filter_combo.currentData())

    if action == "copy":
        _export_deck(deck_id, only_reviewed, None)
    else:
        path = _ask_for_save_path(deck_combo.currentText())
        if path:
            _export_deck(deck_id, only_reviewed, path)


def _open_dialog_for_current_deck() -> None:
    if not mw.col:
        return
    _show_export_dialog(mw.col.decks.get_current_id())


def _add_action_to_menu(menu, deck_id: int) -> None:
    menu.addSeparator()
    action = menu.addAction("Export words...")
    qconnect(action.triggered, lambda: _show_export_dialog(DeckId(int(deck_id))))


# Deck browser: gear/options menu for a specific deck.
def _on_deck_options_menu(menu, deck_id: int) -> None:
    _add_action_to_menu(menu, deck_id)


# Browser sidebar: right-click a deck.
def _on_sidebar_context_menu(sidebar, menu, item, index) -> None:
    if getattr(item, "item_type", None) is None:
        return
    if item.item_type.name != "DECK":
        return
    deck_id = getattr(item, "id", 0)
    if not deck_id:
        return
    _add_action_to_menu(menu, deck_id)


gui_hooks.deck_browser_will_show_options_menu.append(_on_deck_options_menu)
gui_hooks.browser_sidebar_will_show_context_menu.append(_on_sidebar_context_menu)

# Main window: Tools menu entry for the currently selected deck.
_action = QAction("Export words...", mw)
qconnect(_action.triggered, _open_dialog_for_current_deck)
mw.form.menuTools.addAction(_action)
