"""A section click and an action click reach the entire maintenance allowlist."""
import re

from qt_app.catalog import ENTRIES, SECTIONS, SECTION_ACTIONS, palette_entries
from qt_app.feature_catalog import ACTIONS as FEATURE_ACTIONS
from qt_app.i18n import messages
from qt_app.maintenance import ACTIONS as ALL_ACTIONS

# Optional 2.2 feature actions are confirmed by their own pages, not by catalog cards.
ACTIONS = ALL_ACTIONS - FEATURE_ACTIONS.keys()


def test_each_approved_action_has_a_direct_section_destination():
    assert tuple(SECTION_ACTIONS) == SECTIONS == (
        "home", "cleanup", "startup", "repair", "performance", "guided", "history", "updates", "settings"
    )
    direct_actions = {action for actions in SECTION_ACTIONS.values() for action in actions}
    assert direct_actions == ACTIONS == set(ENTRIES)
    assert FEATURE_ACTIONS.keys() <= ALL_ACTIONS
    assert not FEATURE_ACTIONS.keys() & set(ENTRIES)
    assert all(re.fullmatch(r"[a-z_]+", action) for action in direct_actions)
    assert {"quick_cleanup", "restore_point", "windows_update"} <= set(SECTION_ACTIONS["home"])
    assert {"quick_cleanup", "browser_clean", "open_cleanmgr"} <= set(SECTION_ACTIONS["cleanup"])
    assert {"restore_point", "chkdsk", "sfc"} <= set(SECTION_ACTIONS["repair"])


def test_confirmation_titles_and_both_locales_use_the_same_action_ids():
    english, italian = messages("en"), messages("it")
    for section in SECTIONS:
        assert english[f"nav.{section}"] and italian[f"nav.{section}"]
    for action in ACTIONS:
        it_title, en_title, it_description, en_description = ENTRIES[action]
        assert (it_title, en_title) == (italian[f"action.{action}.title"], english[f"action.{action}.title"])
        assert (it_description, en_description) == (
            italian[f"action.{action}.description"], english[f"action.{action}.description"]
        )


def test_palette_contains_one_bilingual_entry_per_section_and_operation():
    entries = palette_entries()
    assert len(entries) == len(SECTIONS) + len(ACTIONS)
    assert {row["section"] for row in entries if not row["action"]} == set(SECTIONS)
    actions = {row["action"]: row for row in entries if row["action"]}
    assert set(actions) == ACTIONS
    assert actions["quick_cleanup"]["section"] == "cleanup"
    assert actions["restore_point"]["section"] == "repair"
    for row in entries:
        if row["action"]:
            assert row["action"] in SECTION_ACTIONS[row["section"]]
        assert row["titles"] == [messages(lang)[row["titleKey"]] for lang in ("it", "en")]
        for lang in ("it", "en"):
            labels = messages(lang)
            assert labels[row["titleKey"]] in row["keywords"]
            if row["descriptionKey"]:
                assert labels[row["descriptionKey"]] in row["keywords"]
