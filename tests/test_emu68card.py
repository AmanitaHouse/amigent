"""#18, #19: Emu68's boot partition, changed only the safe way. On fake cards, never a real one."""

import gzip
import json
import struct

import pytest

import amigent.server as server
from amigent import emu68card as ec
from amigent.channel import Commands
from amigent.emu68card import CardError, FolderCard
from amigent.errors import AmigaError
from fakeamiga import FakeAmiga

MODULES_107 = b"$VER: devicetree 1.5.0 (07.01.2024)\0$VER: brcm-sdhc 1.6.0 (18.10.2024)\0" \
              b"$VER: brcm-emmc 1.5.0 (18.10.2024)\0"
MODULES_111 = b"$VER: devicetree 1.5 (04.11.2025)\0$VER: brcm-sdhc 1.9 (25.04.2026)\0" \
              b"$VER: brcm-emmc 1.8 (22.03.2026)\0"


def kernel(version: str, modules: bytes, size: int = 3000) -> bytes:
    body = b"\0" * 100 + f"$VER: Emu68 {version} (01.01.2026) git:abc\0".encode() + modules
    return body + bytes(range(256)) * (size // 256)


def rom(version=40, revision=68, size=512 * 1024, good=True) -> bytes:
    data = bytearray(size)
    data[:4] = b"\x11\x14\x4e\xf9" if size >= 512 * 1024 else b"\x11\x11\x4e\xf9"
    struct.pack_into(">HH", data, 12, version, revision)
    for i in range(64, size - 64, 97):
        data[i] = i & 0xFF
    total = ec.rom_checksum(bytes(data))
    struct.pack_into(">I", data, size - 24, (~total & 0xFFFFFFFF) if good else 0x1234)
    return bytes(data)


CONFIG = ("# Emu68\nkernel=Emu68-pistorm32lite\narm_64bit=1\nhdmi_force_hotplug=1\n"
          "initramfs kick.rom\n")
CMDLINE = "logo=black vc4.mem=16 sd.unit0=rw\n"


def boot_files(marker=True) -> dict:
    files = {
        "config.txt": CONFIG.encode(),
        "cmdline.txt": CMDLINE.encode(),
        "Emu68-pistorm32lite": kernel("1.0.7", MODULES_107),
        "kick.rom": rom(),
        "start4.elf": b"old start4" * 50,
        "fixup4.dat": b"old fixup",
        "bootcode.bin": b"old bootcode",
        "bcm2711-rpi-4-b.dtb": b"old dtb",
    }
    if marker:
        files[ec.MARKER] = b"yes\n"
    return files


@pytest.fixture
def card(tmp_path):
    root = tmp_path / "card"
    root.mkdir()
    for name, data in boot_files().items():
        (root / name).write_bytes(data)
    return FolderCard(root)


@pytest.fixture
def pc(tmp_path):
    return tmp_path / "pc-backups"


def snapshot(card):
    return {rel: card.read(rel) for rel, _ in card.files() if not ec._ours(rel)}


# ---- options


def test_known_options_and_values_are_checked():
    assert ec.check_option("vc4.mem", "32") == ("vc4.mem", [])
    assert ec.check_option("NOFPU", None)[0] == "nofpu"
    with pytest.raises(CardError, match="not an Emu68 option"):
        ec.check_option("turbo_mode", None)
    assert ec.check_option("turbo_mode", None, force=True)[0] == "turbo_mode"
    with pytest.raises(CardError, match="0 to 1024"):
        ec.check_option("vc4.mem", "lots")
    with pytest.raises(CardError, match="0 \\| 1 \\| 2 \\| 4 \\| 8"):
        ec.check_option("z2_ram_size", "3")
    with pytest.raises(CardError, match="without a value"):
        ec.check_option("nofpu", "1")
    with pytest.raises(CardError, match="needs a value"):
        ec.check_option("sd.unit0", None)
    assert "partition table" in ec.check_option("sd.unit0", "rw")[1][0]
    with pytest.raises(CardError):
        ec.check_option("vc4.mem", "1 2")


def test_set_option_changes_one_word_and_keeps_the_rest():
    text, _ = ec.set_option(CMDLINE, "vc4.mem", "64")
    assert text == "logo=black vc4.mem=64 sd.unit0=rw\n"
    text, _ = ec.set_option("logo=black\r\n", "nofpu", None)
    assert text == "logo=black nofpu\r\n"
    text, _ = ec.set_option(CMDLINE, "sd.unit0", None, remove=True)
    assert text == "logo=black vc4.mem=16\n"
    with pytest.raises(CardError, match="not in cmdline.txt"):
        ec.set_option(CMDLINE, "nofpu", None, remove=True)
    with pytest.raises(CardError, match="more than one line"):
        ec.set_option("a\nb\n", "nofpu", None)
    assert ec.set_option("SC SCS=2", "SC", None)[0] == "SC SCS=2"  # short forms are names of their own


# ---- the marker, the dry run, the backup


def test_without_the_marker_nothing_is_written(card, pc):
    card.delete(ec.MARKER)
    before = snapshot(card)
    with pytest.raises(CardError, match="only reads it"):
        ec.change_option(card, pc, "vc4.mem", "32", confirm=True)
    assert "Writing would be refused" in ec.change_option(card, pc, "vc4.mem", "32")
    assert "Writing would be refused" in ec.update(card, archive_111(), pc, videocore=(1, 5))
    assert snapshot(card) == before and not pc.exists()


def test_a_dry_run_shows_the_plan_and_writes_nothing(card, pc):
    before = snapshot(card)
    text = ec.change_option(card, pc, "vc4.mem", "32")
    assert "Dry run" in text and "cmdline.txt: replaced" in text and "untested on real hardware" in text
    assert snapshot(card) == before and not pc.exists()


def test_a_change_is_backed_up_twice_verified_and_undone(card, pc):
    text = ec.change_option(card, pc, "vc4.mem", "32", confirm=True)
    assert "read back" in text and "next start" in text
    assert card.read("cmdline.txt") == b"logo=black vc4.mem=32 sd.unit0=rw\n"
    [b] = ec.backups(pc)
    manifest, data = ec.load_backup(b["folder"])
    assert data == {"cmdline.txt": CMDLINE.encode()} and not manifest["full"]
    on_card = f"{ec.BACKUPS}/{b['id']}"
    assert card.read(f"{on_card}/files/cmdline.txt") == CMDLINE.encode()
    assert json.loads(card.read(f"{on_card}/{ec.MANIFEST}"))["files"][0]["sha256"] == manifest["files"][0]["sha256"]
    assert b"card reader" in card.read(f"{on_card}/{ec.README}")
    assert not [r for r, _ in card.files() if r.endswith((ec.NEW, ec.OLD))]
    # only cmdline.txt and the backup folder changed
    assert {r for r, _ in card.files() if not ec._ours(r)} == set(boot_files())

    assert "Dry run" in ec.undo(card, pc)
    assert card.read("cmdline.txt") != CMDLINE.encode()
    ec.undo(card, pc, b["id"], confirm=True)
    assert card.read("cmdline.txt") == CMDLINE.encode()
    assert len(ec.backups(pc)) == 2  # the undo backed up what it replaced


class NoCopyCard(FolderCard):
    def copy(self, src, dst):
        raise OSError("disk full")


def test_a_failed_backup_stops_before_anything_is_written(card, pc):
    broken = NoCopyCard(card.root)
    before = snapshot(broken)
    with pytest.raises(CardError, match="refused: the backup failed.*nothing on the card was changed"):
        ec.change_option(broken, pc, "vc4.mem", "32", confirm=True)
    assert snapshot(broken) == before


class BadWriteCard(FolderCard):
    """A card that loses a byte on writing: what a flaky card or a cut write looks like."""

    def write(self, rel, data):
        if rel.endswith(ec.NEW) and data:
            data = bytes([data[0] ^ 0xFF]) + data[1:]
        super().write(rel, data)


def test_a_write_that_does_not_read_back_replaces_nothing(card, pc):
    broken = BadWriteCard(card.root)
    with pytest.raises(CardError, match="did not read back the same; nothing was replaced"):
        ec.change_option(broken, pc, "vc4.mem", "32", confirm=True)
    assert card.read("cmdline.txt") == CMDLINE.encode()
    assert not [r for r, _ in card.files() if r.endswith((ec.NEW, ec.OLD))]


class BadSwapCard(FolderCard):
    """Fine until the new file takes the old one's name, then the result reads wrong."""

    def rename(self, old, new):
        super().rename(old, new)
        if old.endswith(ec.NEW):
            path = self._find(new)
            path.write_bytes(b"garbage")


def test_a_bad_swap_puts_the_old_file_back(card, pc):
    broken = BadSwapCard(card.root)
    with pytest.raises(CardError, match="put back: cmdline.txt"):
        ec.change_option(broken, pc, "vc4.mem", "32", confirm=True)
    assert card.read("cmdline.txt") == CMDLINE.encode()


def test_backup_and_plan_never_touch_our_folders_or_pistormboot(card, pc):
    with pytest.raises(CardError, match="not a file Amigent writes"):
        ec.apply(card, {f"{ec.BACKUPS}/x": b"1"}, kind="t", what="t", pc_root=pc, confirm=True)
    with pytest.raises(CardError, match="not a file Amigent writes"):
        ec.apply(card, {"PiStormBoot/slot1": b"1"}, kind="t", what="t", pc_root=pc, confirm=True)
    with pytest.raises(CardError, match="not a plain path"):
        ec.apply(card, {"../outside": b"1"}, kind="t", what="t", pc_root=pc, confirm=True)


# ---- Kickstart


def test_kickstart_files_are_checked():
    assert ec.check_kickstart(rom())[0] == "Kickstart 40.68, 512 KB"
    assert ec.check_kickstart(rom(34, 5, 256 * 1024))[0] == "Kickstart 34.5, 256 KB"
    with pytest.raises(CardError, match="checksum is wrong"):
        ec.check_kickstart(rom(good=False))
    assert "checksum_rom" in ec.check_kickstart(rom(good=False), fix_checksum=True)[1][0]
    with pytest.raises(CardError, match="256, 512, 1024 or 2048 KB"):
        ec.check_kickstart(rom()[:300000])
    swapped = bytearray(rom())
    swapped[0::2], swapped[1::2] = swapped[1::2], swapped[0::2]
    with pytest.raises(CardError, match="byte swapped"):
        ec.check_kickstart(bytes(swapped))
    with pytest.raises(CardError, match="Cloanto"):
        ec.check_kickstart(b"AMIROMTYPE1" + bytes(512 * 1024 - 11))
    with pytest.raises(CardError, match="does not start like"):
        ec.check_kickstart(bytes(512 * 1024))


def test_swapping_the_kickstart_and_back(card, pc):
    new = rom(47, 115)
    text = ec.change_kickstart(card, pc, "kick32.rom", new, confirm=True)
    assert "Kickstart 47.115" in text and "kick.rom stays on the card" in text
    assert card.read("kick32.rom") == new and card.read("kick.rom") == rom()
    assert card.read("config.txt").decode() == CONFIG.replace("initramfs kick.rom", "initramfs kick32.rom")
    [b] = ec.backups(pc)
    assert b["absent"] == ["kick32.rom"]
    text = ec.change_kickstart(card, pc, "kick.rom", confirm=True)
    assert card.read("config.txt").decode() == CONFIG
    with pytest.raises(CardError, match="checksum is wrong"):
        ec.change_kickstart(card, pc, "bad.rom", rom(good=False), confirm=True)
    assert card.size("bad.rom") is None


def test_the_fpga_file_before_the_rom_stays(card, pc):
    card.write("config.txt", b"kernel=Emu68-pistorm32lite\ninitramfs fw.bin.gz,kick.rom\n")
    card.write("fw.bin.gz", b"fpga")
    card.write("other.rom", rom(47, 1))
    text = ec.change_kickstart(card, pc, "other.rom", confirm=True)
    assert "fw.bin.gz before the ROM stays" in text
    assert card.read("config.txt") == b"kernel=Emu68-pistorm32lite\ninitramfs fw.bin.gz,other.rom\n"
    assert card.read("fw.bin.gz") == b"fpga"


def test_overview_reads_everything_and_writes_nothing(card):
    before = snapshot(card)
    text = ec.overview(card, check=True)
    assert "Emu68 1.0.7, for PiStorm32-lite or PiStorm16" in text
    assert "kick.rom (Kickstart 40.68, 512 KB)" in text
    assert "vc4.mem=16: MB of VideoCore memory" in text and "partition table" in text
    assert "changes: allowed" in text and "9 fine, 0 with errors" in text
    assert snapshot(card) == before
    card.delete("kick.rom")
    assert "kick.rom named by initramfs in config.txt is not on the card" in ec.overview(card)


# ---- the update


def archive_111(variant_name="Emu68-pistorm.gz"):
    return {
        variant_name: gzip.compress(kernel("1.1.0-beta.1", MODULES_111, 5000)),
        "start4.elf": b"new start4" * 60,
        "fixup4.dat": b"new fixup",
        "bootcode.bin": b"old bootcode",  # the same: not written
        "bcm2711-rpi-4-b.dtb": b"new dtb",
        "overlays/emu68.dtbo": b"dtbo",
        "config.txt": b"kernel=Emu68-pistorm.gz\ninitramfs kick.rom\n",  # the card keeps its own
        "README.md": b"hello",
    }


def test_versions_variants_and_modules_from_the_kernel():
    k = archive_111()["Emu68-pistorm.gz"]
    assert ec.kernel_version(k) == "1.1.0-beta.1"
    assert ec.embedded_modules(k)["brcm-sdhc.device"] == (1, 9)
    assert ec.variant("Emu68-pistorm", "1.0.7") == "pistorm-classic"
    assert ec.variant("Emu68-pistorm.gz", "1.1.0-beta.1") == "pistorm32"
    assert ec.variant("Emu68-pistorm32lite", "1.0.7") == "pistorm32"
    assert ec.version_tuple("1.1.0-beta.1") < ec.version_tuple("1.1.0") < ec.version_tuple("1.1.1")


def test_an_update_stops_when_the_videocore_driver_does_not_fit(card, pc):
    before = snapshot(card)
    text = ec.update(card, archive_111(), pc, videocore=(1, 2), confirm=True)
    assert "Stop: VideoCore.card 1.2 does not fit Emu68 1.1.0-beta.1, which needs 1.5 or newer" in text
    assert snapshot(card) == before and not pc.exists()


def test_an_update_stops_for_another_board_or_the_same_version(card, pc):
    text = ec.update(card, archive_111("Emu68-pistorm-classic.gz"), pc, videocore=(1, 5), confirm=True)
    assert "Stop: the archive is for PiStorm with CPLD" in text
    same = {"Emu68-pistorm32lite": kernel("1.0.7", MODULES_107)}
    assert "Stop: Emu68 1.0.7 is on the card already" in ec.update(card, same, pc, videocore=None)


def test_an_update_backs_up_everything_then_installs_and_confirms(card, pc):
    before = snapshot(card)
    dry = ec.update(card, archive_111(), pc, videocore=(1, 5))
    assert "Dry run" in dry and "power off and on brings back nothing" in dry.replace("switching the ", "")
    assert "second SD card" in dry and "kernel=Emu68-pistorm32lite -> kernel=Emu68-pistorm.gz" in dry
    assert "vc4.mem" in dry  # options that moved to overlays in 1.1
    assert snapshot(card) == before

    text = ec.update(card, archive_111(), pc, videocore=(1, 5), confirm=True)
    assert "amiga_emu68_update(after_restart=True)" in text
    assert card.read("start4.elf") == b"new start4" * 60
    assert card.read("overlays/emu68.dtbo") == b"dtbo"
    assert card.read("config.txt") == CONFIG.replace("kernel=Emu68-pistorm32lite", "kernel=Emu68-pistorm.gz").encode()
    for untouched in ("cmdline.txt", "kick.rom", "Emu68-pistorm32lite", ec.MARKER):
        assert card.read(untouched) == before[untouched]
    assert card.size("README.md") is None
    [b] = ec.backups(pc)
    manifest, data = ec.load_backup(b["folder"])
    assert manifest["full"] and data == before
    assert ec.load_backup(card.root / ec.BACKUPS / b["id"])[1] == before  # the card's copy, checked too

    assert "Not confirmed" in ec.confirm_update(pc, {"brcm-sdhc.device": (1, 6)})
    assert "Confirmed: Emu68 1.1.0-beta.1" in ec.confirm_update(pc, {"brcm-sdhc.device": (1, 9)})
    assert "No Emu68 update is waiting" in ec.confirm_update(pc, {})


def test_the_update_refuses_without_room_for_the_backup(card, pc, monkeypatch):
    monkeypatch.setattr(FolderCard, "free", lambda self: 1000)
    with pytest.raises(CardError, match="KB free on the card"):
        ec.update(card, archive_111(), pc, videocore=(1, 5), confirm=True)
    assert not pc.exists() or not ec.backups(pc)


def test_archives_with_paths_outside_are_refused(tmp_path):
    import zipfile
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../../evil", b"x")
    with pytest.raises(CardError, match="points outside"):
        ec.read_archive(bad)
    good = tmp_path / "good.zip"
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("Emu68/start4.elf", b"s")
        z.writestr("Emu68/overlays/x.dtbo", b"d")
    assert ec.read_archive(good) == {"start4.elf": b"s", "overlays/x.dtbo": b"d"}


# ---- the rescue on the PC


def test_restore_on_the_pc_after_a_bad_update(card, pc, capsys):
    before = snapshot(card)
    ec.update(card, archive_111(), pc, videocore=(1, 5), confirm=True)
    [b] = ec.backups(pc)
    assert ec.main(["restore", str(b["folder"]), str(card.root)]) == 0
    assert "Dry run" in capsys.readouterr().out and card.read("start4.elf") != before["start4.elf"]
    assert ec.main(["restore", str(b["folder"]), str(card.root), "--yes"]) == 0
    out = capsys.readouterr().out
    assert "overlays/emu68.dtbo" in out  # named as staying, not deleted
    assert snapshot(card) == {**before, "Emu68-pistorm.gz": card.read("Emu68-pistorm.gz"),
                              "overlays/emu68.dtbo": b"dtbo"}
    assert ec.main(["restore", str(b["folder"]), str(card.root)]) == 0
    assert "nothing to do" in capsys.readouterr().out
    # the card's own copy works just as well, as from a card reader with no PC backup
    assert ec.main(["verify", str(card.root / ec.BACKUPS / b["id"])]) == 0


def test_restore_refuses_a_damaged_backup_or_a_strange_folder(card, pc, tmp_path, capsys):
    ec.change_option(card, pc, "vc4.mem", "32", confirm=True)
    [b] = ec.backups(pc)
    home = tmp_path / "home"
    home.mkdir()
    (home / "notes.txt").write_text("mine")
    assert ec.main(["restore", str(b["folder"]), str(home), "--yes"]) == 1
    assert "does not look like a Pi boot partition" in capsys.readouterr().err
    assert (home / "notes.txt").read_text() == "mine" and len(list(home.iterdir())) == 1
    (b["folder"] / "files" / "cmdline.txt").write_bytes(b"tampered")
    assert ec.main(["restore", str(b["folder"]), str(card.root), "--yes"]) == 1
    assert "does not match its checksum" in capsys.readouterr().err
    assert card.read("cmdline.txt") == b"logo=black vc4.mem=32 sd.unit0=rw\n"


# ---- through amigentd, on the fake Amiga


def fake_amiga(marker=True, emu68=True):
    fake = FakeAmiga()
    fake.protocol = 6
    for name, data in boot_files(marker).items():
        fake.add(f"BOOT:{name}", data)
    fake.volume_lines = ["System:\t1000\t2000\t3000\t512", "BOOT:\t9000000\t400000000\t409000000\t512"]
    fake.loaded = ["L\texec.library\t47\t115\t40\t00000ac0\t1032\t632\texec 47.115",
                   "D\tbrcm-sdhc.device\t1\t6\t1\t0a100000\t60\t60\t"]
    if emu68:
        fake.loaded.append("R\tdevicetree.resource\t1\t5\t0\t0a200000\t60\t60\t")
    return fake


@pytest.fixture
def on(machine_session):
    made = []

    def use(fake):
        made.append(fake)
        machine_session.ctl.close()
        machine_session.ctl = Commands("127.0.0.1", 1, fake.port)
        return fake
    yield use
    machine_session.ctl.close()
    for fake in made:
        fake.close()


def test_the_tools_find_the_card_and_change_an_option_on_the_amiga(on):
    fake = on(fake_amiga())
    text = server.amiga_emu68_card()
    assert "Emu68 boot partition BOOT:" in text and "Emu68 1.0.7" in text
    assert "Dry run" in server.amiga_emu68_option("vc4.mem", "32")
    assert fake.files["BOOT:cmdline.txt"] == CMDLINE.encode()
    text = server.amiga_emu68_option("vc4.mem", "32", confirm=True)
    assert "written and read back" in text
    assert fake.files["BOOT:cmdline.txt"] == b"logo=black vc4.mem=32 sd.unit0=rw\n"
    copies = [p for p in fake.files if p.startswith("BOOT:amigent-backup/") and p.endswith("/files/cmdline.txt")]
    assert len(copies) == 1 and fake.files[copies[0]] == CMDLINE.encode()
    assert not [p for p in fake.files if p.endswith((ec.NEW, ec.OLD))]
    server.amiga_emu68_undo(confirm=True)
    assert fake.files["BOOT:cmdline.txt"] == CMDLINE.encode()
    assert "nofpu: no FPU" in server.amiga_emu68_option()


def test_on_the_amiga_a_write_that_reads_back_wrong_changes_nothing(on):
    fake = on(fake_amiga())
    fake.corrupt.add("BOOT:cmdline.txt" + ec.NEW)
    with pytest.raises(AmigaError, match="nothing was replaced"):
        server.amiga_emu68_option("vc4.mem", "32", confirm=True)
    assert fake.files["BOOT:cmdline.txt"] == CMDLINE.encode()


def test_on_the_amiga_without_marker_or_emu68_nothing_is_written(on):
    on(fake_amiga(marker=False))
    with pytest.raises(AmigaError, match="only reads it"):
        server.amiga_emu68_option("vc4.mem", "32", confirm=True)
    assert "not allowed, read only" in server.amiga_emu68_card()
    other = on(fake_amiga(emu68=False))
    with pytest.raises(AmigaError, match="does not run Emu68"):
        server.amiga_emu68_card()
    assert other.files["BOOT:cmdline.txt"] == CMDLINE.encode()


def test_on_the_amiga_a_kickstart_comes_from_an_amiga_path(on):
    fake = on(fake_amiga())
    fake.add("DEVS:Kickstarts/kick47.rom", rom(47, 115))
    server.amiga_emu68_kickstart("DEVS:Kickstarts/kick47.rom", confirm=True)
    assert fake.files["BOOT:kick47.rom"] == rom(47, 115)
    assert b"initramfs kick47.rom" in fake.files["BOOT:config.txt"]


def test_on_the_amiga_the_update_checks_videocore_and_confirms(on, tmp_path):
    fake = on(fake_amiga())
    folder = tmp_path / "release"
    for name, data in archive_111().items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    fake.answers["Version FILE LIBS:Picasso96/VideoCore.card"] = (0, "VideoCore.card 1.2 (01.01.2024)\n")
    assert "Stop: VideoCore.card 1.2" in server.amiga_emu68_update(str(folder), confirm=True)
    fake.answers["Version FILE LIBS:Picasso96/VideoCore.card"] = (0, "VideoCore.card 1.5 (01.09.2026)\n")
    text = server.amiga_emu68_update(str(folder), confirm=True)
    assert "of the whole boot partition" in text
    assert fake.files["BOOT:start4.elf"] == b"new start4" * 60
    assert any(p.endswith("/README.txt") for p in fake.files if p.startswith("BOOT:amigent-backup/"))
    assert "Not confirmed" in server.amiga_emu68_update(after_restart=True)
    fake.loaded[1] = "D\tbrcm-sdhc.device\t1\t9\t1\t0a100000\t60\t60\t"
    assert "Confirmed" in server.amiga_emu68_update(after_restart=True)


def test_a_comment_line_above_the_options_is_kept_and_not_read_as_options():
    from amigent.emu68card import parse_cmdline, set_option
    text = "# https://example.org/#emu68\nlogo=black vc4.mem=16 sd.unit0=rw\n"
    assert parse_cmdline(text) == [("logo", "black"), ("vc4.mem", "16"), ("sd.unit0", "rw")]
    new, _ = set_option(text, "sd.unit0", "ro")
    assert new == "# https://example.org/#emu68\nlogo=black vc4.mem=16 sd.unit0=ro\n"
