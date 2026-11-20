"""Connected daemon identity in the viewer, separate from the computer."""

from amigent.daemons import describe_connected
from amigent.paths import AMIGA

BIN = AMIGA / "bin"


def test_describe_connected_keeps_machine_and_file_identity_apart():
    classic = (BIN / "amigentd").read_bytes()
    on_fast = describe_connected(6, "amigentd 1.4.0", classic,
                                 {"os": "AmigaOS", "cpu": "68060", "loaded": "1"}, BIN)
    assert on_fast["daemon_family"] == "general"
    assert on_fast["daemon_target"] == "68020"
    assert on_fast["daemon_identity"] == "named file"
    assert on_fast["daemon_protocol"] == 6
    assert "loaded" in on_fast["daemon_capabilities"]
    unnamed = describe_connected(5, "", None, {"os": "AmigaOS", "cpu": "68040"}, BIN)
    assert unnamed["daemon_family"] == "Not reported"
    assert unnamed["daemon_identity"] == "Not reported"
    assert unnamed["daemon_version"] == "Not reported"
    assert unnamed["daemon_protocol"] == 5


def test_about_dialog_localises_the_new_daemon_rows():
    import json
    import re
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "src" / "amigent" / "web"
    page = (web / "index.html").read_text(encoding="utf-8")
    script = (web / "viewer.js").read_text(encoding="utf-8")
    english = json.loads((web / "locales" / "en.json").read_text(encoding="utf-8"))
    for key in ("about_daemon", "about_protocol", "about_daemon_cpu", "about_capabilities",
                "not_reported", "named_file"):
        assert key in english
    assert 'data-i18n="about_daemon"' in page
    assert "daemon_family" in script and 't("named_file")' in script
    used = set(re.findall(r'data-i18n(?:-title|-label|-aria)?="([a-z_]+)"', page))
    used |= set(re.findall(r'\bt\("([a-z_]+)"', script))
    assert {"about_daemon", "about_protocol", "about_daemon_cpu", "about_capabilities",
            "not_reported", "named_file"} <= used
    assert used <= english.keys()
