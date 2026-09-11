#!/usr/bin/python3
"""Stamp this pane with the Claude session id running in it.

herdr keeps one `agent_session` ref per pane, readable back as a typed field
(`pane.agent_session.value`). Writing it here is what lets a sweeper find a
pane's own transcript without reading the screen, and it is the only thing
that works for a pane whose agent carries no name -- a session started by
hand or from the phone, which no delegating launcher ever named.

Registered on two events. SessionStart fires with no prompt, so a pane is
linked the moment it opens; UserPromptSubmit re-asserts the link if the pane
record ever lost it (herdr restarted, authority cleared, hook installed
mid-session). The read-back guard makes the steady state one socket round
trip and no write.

Fails closed in every direction: no stdout (UserPromptSubmit stdout is
injected into the model's context), never a non-zero exit, no exception
escapes. An unstamped pane is merely unsweepable, which is the safe side.

WHY IT LIVES IN THIS SKILL. Every reader of the field it writes is in this
repository -- campaign-role-brief.py resolves a session's role through it,
check-campaign-claim.py its licence, campaign-claim.py its liveness -- so the
writer sits beside them, and scripts/install-hooks.sh registers it machine-wide
on both events, as it does campaign-role-brief.py. It is ours and not herdr's:
the vendored SKILL.md above is upstream's and untouched, and herdr's own
integration, ~/.claude/hooks/herdr-agent-state.sh, stays where herdr put it.
"""
import json
import os
import socket
import subprocess
import sys
import time

SOURCE = "herdr:claude"  # herdr's own integration id; the authority key
AGENT = "claude"
TIMEOUT_S = 3.0


def rpc(method, params):
    """One request/response over herdr's unix socket. Raises on any trouble."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(TIMEOUT_S)
        s.connect(os.environ["HERDR_SOCKET_PATH"])
        s.sendall((json.dumps({
            "id": "session-link:%d" % os.getpid(),
            "method": method,
            "params": params,
        }) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf.decode() or "{}")


def linked_id(pane_id):
    """The session id herdr currently holds for this pane, or None."""
    pane = ((rpc("pane.get", {"pane_id": pane_id}).get("result") or {})
            .get("pane") or {})
    session = pane.get("agent_session") or {}
    return session.get("value") if session.get("kind") == "id" else None


def parent_of(pid):
    out = subprocess.run(["ps", "-p", str(pid), "-o", "ppid="],
                         capture_output=True, text=True, timeout=5)
    text = out.stdout.strip()
    return int(text) if text.isdigit() else None


def is_the_panes_own_session(pane_id):
    """True when this hook belongs to the session the pane is running.

    A one-shot `claude -p` started from inside a pane fires SessionStart too,
    and stamping on it would replace the pane's link with a throwaway
    session's -- pointing every later verdict at the wrong record. The pane's
    own agent is the claude the shell started, so walk up from this hook to
    the claude that owns it and require that one to be the shell's child.
    """
    shell_pid = rpc("pane.process_info", {"pane_id": pane_id}) \
        .get("result", {}).get("process_info", {}).get("shell_pid")
    if not shell_pid:
        return False
    pid = os.getppid()
    for _ in range(8):                  # hooks sit a few frames under claude
        parent = parent_of(pid)
        if parent is None:
            return False
        if parent == shell_pid:
            return True
        pid = parent
    return False


def report(pane_id, session_id):
    rpc("pane.report_agent_session", {
        "pane_id": pane_id,
        "source": SOURCE,
        "agent": AGENT,
        "seq": time.time_ns(),
        "agent_session_id": session_id,
    })


def main():
    hook = json.loads(sys.stdin.read() or "{}")
    # A subagent shares the pane with its parent; only the parent's own
    # session id belongs on the pane record.
    if hook.get("agent_id"):
        return
    session_id = hook.get("session_id")
    pane_id = os.environ.get("HERDR_PANE_ID")
    if not (session_id and pane_id and os.environ.get("HERDR_SOCKET_PATH")):
        return
    if linked_id(pane_id) == session_id:
        return
    if not is_the_panes_own_session(pane_id):
        return
    report(pane_id, session_id)
    if linked_id(pane_id) == session_id:
        return
    # A stale value from this same source outranked the write -- herdr keeps
    # the first writer per source and says nothing. Drop the claim, restate
    # it once, and stop either way.
    rpc("pane.clear_agent_authority",
        {"pane_id": pane_id, "source": SOURCE, "seq": time.time_ns()})
    report(pane_id, session_id)


try:
    main()
except Exception:
    pass
sys.exit(0)
