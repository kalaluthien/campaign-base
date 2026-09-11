#!/usr/bin/env python3
# witnesses: Cov_Stamp, Q13b_RestampedSessionActs
"""Prove herdr-session-link.py stamps the pane's own session and nothing else.

Each case runs the hook as the harness does -- a process, the hook payload on
stdin, HERDR_PANE_ID and HERDR_SOCKET_PATH in its environment -- against a fake
herdr serving the four socket methods the hook calls, and asserts on what the
fake was ASKED and what the pane record holds afterwards.

The process chain is real, because the own-session check walks it with `ps`:
this test process plays the pane's shell, and the hook is started under a hop
named `claude` -- a symlink to this interpreter, which `ps` reports by that
name -- so the chain reads `hook <- claude <- shell` the way a live one does.

Every case also asserts the hook's contract with the harness: exit 0 and no
stdout, since UserPromptSubmit stdout is injected into the model's context.

Usage: .claude/skills/herdr/scripts/herdr-session-link-test.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "herdr-session-link.py"
PANE = "w1:p1"
SID = "11111111-aaaa-bbbb-cccc-000000000001"
OTHER = "22222222-aaaa-bbbb-cccc-000000000002"
# Runs the rest of its argv as a child and waits, so the hop stays in the chain.
HOP = "import subprocess, sys; sys.exit(subprocess.run(sys.argv[1:]).returncode)"


class FakeHerdr:
    """The four methods the hook calls, over a unix socket.

    `sticky` is herdr's first-writer-per-source rule: while the source holds
    authority over the pane, a report from it is dropped without a word, and
    only `pane.clear_agent_authority` lets the next one land."""

    def __init__(self, path, shell_pid, linked=None, sticky=False):
        self.path, self.shell_pid = path, shell_pid
        self.linked, self.sticky, self.authority = linked, sticky, linked is not None
        self.calls = []
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen(8)
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                req = json.loads(buf.decode())
                conn.sendall((json.dumps(self.handle(req)) + "\n").encode())

    def handle(self, req):
        method, params = req["method"], req.get("params") or {}
        self.calls.append((method, params))
        if method == "pane.get":
            session = {"kind": "id", "value": self.linked} if self.linked else None
            return {"result": {"pane": {"pane_id": PANE, "agent_session": session}}}
        if method == "pane.process_info":
            return {"result": {"process_info": {"shell_pid": self.shell_pid}}}
        if method == "pane.report_agent_session":
            if not (self.sticky and self.authority):
                self.linked = params["agent_session_id"]
                self.authority = True
            return {"result": {}}
        if method == "pane.clear_agent_authority":
            self.authority = False
            return {"result": {}}
        return {"error": {"message": f"unknown method {method}"}}

    def methods(self):
        return [m for m, _ in self.calls]

    def close(self):
        self.sock.close()


def run(tmp, payload, hops=("claude",), shell_pid=None, env_extra=None,
        drop_env=(), **fake):
    """Run the hook under `hops`, this process standing as the pane's shell
    unless `shell_pid` names another. Returns (process, fake)."""
    sock = os.path.join(tmp, f"h{len(os.listdir(tmp))}.sock")
    herdr = FakeHerdr(sock, os.getpid() if shell_pid is None else shell_pid, **fake)
    claude = os.path.join(tmp, "claude")
    if not os.path.exists(claude):
        os.symlink(sys.executable, claude)
    argv = [sys.executable, str(HOOK)]
    for hop in reversed(hops):
        if hop == "claude":
            argv = [claude, "-c", HOP] + argv
        else:                                   # a shell that does not exec its last command
            argv = ["/bin/sh", "-c", '"$@"; exit $?', "sh"] + argv
    env = dict(os.environ, HERDR_PANE_ID=PANE, HERDR_SOCKET_PATH=sock)
    env.update(env_extra or {})
    for k in drop_env:
        env.pop(k, None)
    body = payload if isinstance(payload, str) else json.dumps(payload)
    p = subprocess.run(argv, input=body, capture_output=True, text=True,
                       env=env, timeout=30)
    herdr.close()
    return p, herdr


def main():
    ran, fails = [], []

    def check(name, cond, detail=""):
        ran.append(name)
        if not cond:
            fails.append(f"{name}: {detail}")

    def quiet(name, p):
        check(f"{name} -- exits 0 and prints nothing",
              p.returncode == 0 and p.stdout == "",
              f"exit {p.returncode}; stdout {p.stdout!r}; stderr {p.stderr[-200:]!r}")

    # A short directory: a unix socket path is capped near 104 bytes on macOS.
    tmp = tempfile.mkdtemp(prefix="hsl", dir="/tmp")
    try:
        # 1. The ordinary start: an empty pane, its own session. Cov_Stamp.
        p, h = run(tmp, {"session_id": SID, "hook_event_name": "SessionStart"})
        quiet("an empty pane", p)
        check("an empty pane is stamped with its own session's id",
              h.linked == SID and "pane.report_agent_session" in h.methods(),
              str(h.calls))

        # 2. The steady state: the read-back guard makes it one read, no write.
        p, h = run(tmp, {"session_id": SID}, linked=SID)
        quiet("a pane already stamped", p)
        check("a pane already carrying this session writes nothing",
              h.methods() == ["pane.get"], str(h.methods()))

        # 3. The record was lost -- herdr restarted, authority cleared -- and the
        #    next prompt restores it. Q13b's re-stamp.
        p, h = run(tmp, {"session_id": SID, "hook_event_name": "UserPromptSubmit"},
                   linked=None)
        quiet("a pane whose record was lost", p)
        check("a lost stamp is restored on the next prompt", h.linked == SID,
              str(h.calls))

        # 4. A stale value from the same source outranks the write: the hook
        #    clears the authority and states it once more.
        p, h = run(tmp, {"session_id": SID}, linked=OTHER, sticky=True)
        quiet("a stale stamp herdr will not overwrite", p)
        check("a stale stamp is cleared and restated",
              h.linked == SID and h.methods().count("pane.clear_agent_authority") == 1
              and h.methods().count("pane.report_agent_session") == 2,
              str(h.methods()))

        # 5. A plain overwrite lands on the first report, so no clear is sent.
        p, h = run(tmp, {"session_id": SID}, linked=OTHER)
        check("a stamp herdr accepts is not followed by a clear",
              h.linked == SID and "pane.clear_agent_authority" not in h.methods(),
              str(h.methods()))

        # 6. A subagent shares its parent's pane: nothing is read or written.
        p, h = run(tmp, {"session_id": OTHER, "agent_id": "a1"}, linked=SID)
        quiet("a subagent", p)
        check("a subagent's hook leaves the pane alone",
              h.linked == SID and h.calls == [], str(h.calls))

        # 7. A session that is not the pane's own: its claude is not the
        #    shell's child.
        p, h = run(tmp, {"session_id": OTHER}, linked=None, shell_pid=2 ** 22 + 7)
        quiet("a session of another pane", p)
        check("a session that is not the pane's own does not stamp it",
              h.linked is None and "pane.report_agent_session" not in h.methods(),
              str(h.methods()))

        # 8. A one-shot `claude -p` run from the pane's own session's Bash
        #    tool: its hook sits under its claude, a tool shell, and then the
        #    pane's claude, which IS the shell's child -- so a walk that goes
        #    far enough finds the shell and stamps the throwaway id.
        p, h = run(tmp, {"session_id": OTHER}, hops=("claude", "sh", "claude"),
                   linked=SID)
        quiet("a one-shot inside the pane", p)
        check("a one-shot claude inside the pane leaves the pane's stamp alone",
              h.linked == SID and "pane.report_agent_session" not in h.methods(),
              str(h.methods()))
        # ...while the pane's own session still stamps through one wrapper
        # frame, the spare the walk keeps for a harness that runs its hooks
        # under a shell.
        p, h = run(tmp, {"session_id": SID}, hops=("claude", "sh"))
        check("the pane's own session stamps through a shell wrapper",
              h.linked == SID, str(h.methods()))

        # 9. Outside herdr: no pane, no socket, no payload -- all silent.
        p, h = run(tmp, {"session_id": SID}, drop_env=("HERDR_PANE_ID",))
        quiet("no HERDR_PANE_ID", p)
        check("no HERDR_PANE_ID asks herdr nothing", h.calls == [], str(h.calls))
        p, h = run(tmp, {"session_id": SID},
                   env_extra={"HERDR_SOCKET_PATH": os.path.join(tmp, "absent.sock")})
        quiet("a socket that is not there", p)
        p, h = run(tmp, "not json")
        quiet("a payload that is not JSON", p)
        check("a payload that is not JSON asks herdr nothing", h.calls == [],
              str(h.calls))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for f in fails:
        print(f"FAIL  {f}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
