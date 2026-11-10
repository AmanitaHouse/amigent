"""Other agents on the same Amiga: found by port and task names, said once."""

from amigent import others


class Ctl:
    def __init__(self, present=(), startup=False):
        self.present, self.startup = set(present), startup

    def exec(self, command, timeout=30):
        class R:
            pass
        r = R()
        if command.startswith("Search"):
            word = "amiagent" if self.startup is True else self.startup
            r.rc = 0 if word and f" {word} " in command else 5
        else:
            r.rc = 0 if any(f'"{p}"' in command for p in self.present) else 20
        return r


def test_a_running_amiagent_is_found_by_its_port_and_task():
    found = others.from_sysinfo({"ports": "REXX|AMIAGENT|AMIGENT", "tasks": "amiagent|input.device"})
    assert [f.agent.name for f in found] == ["amiagent"]
    assert found[0].running and "port AMIAGENT" in found[0].how
    assert "amiagent" in others.warning(found)


def test_nothing_running_means_no_warning():
    assert others.from_sysinfo({"ports": "REXX|AMIGENT", "tasks": "Workbench"}) == []
    assert others.warning([]) == ""


def test_installed_but_not_running_is_reported_without_a_warning():
    found = others.scan(Ctl(present=["C:amiagent"], startup=True), "", {"ports": "", "tasks": ""})
    assert len(found) == 1 and not found[0].running
    assert "installed as C:amiagent" in found[0].how and "started from S:User-Startup" in found[0].how
    assert others.warning(found) == ""


def test_the_status_window_alone_counts_as_running():
    found = others.from_sysinfo({"ports": "", "tasks": "amimon-mui"})
    assert found and found[0].agent.name == "amimon" and found[0].running


def test_the_devbench_bridge_is_found_running_and_installed():
    found = others.from_sysinfo({"ports": "REXX|AMIGABRIDGE", "tasks": "amiga-bridge"})
    assert [f.agent.name for f in found] == ["amiga-bridge"]
    assert "amiga-bridge" in others.warning(found)
    found = others.scan(Ctl(present=["DH0:AmigaBridge/amiga-bridge"], startup="amiga-bridge"), "",
                        {"ports": "", "tasks": ""})
    assert [f.agent.name for f in found] == ["amiga-bridge"]
    assert not found[0].running and "started from S:User-Startup" in found[0].how


def test_ports_on_this_pc_are_not_taken_for_an_emulated_amigas():
    assert others.loopback("127.0.0.1") and others.loopback("localhost")
    assert not others.loopback("192.0.2.7")
