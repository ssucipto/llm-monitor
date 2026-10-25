# Architecture Decision Records (ADR Log)
# Loaded by section (ADR ID) only — never fully loaded
# Add entries via /acp-decide command

## ADR-LM-001 | 2026-10-17 | Cross-session control of the dashboard supervisor
**Status:** Accepted
**Context:** DECISION B runs the supervisor at startup through an S4U task, in session 0. Tested in audit-27: from the desktop, session-0 processes show no command line, path or start time, and Stop-Process on them is Access denied; Stop-ScheduledTask stopped only the supervisor and left the server running. Restarts after a reboot were impossible, and every stop could leave an orphan.
**Options considered:** (1) revert to logon-only (re-opens DECISION B); (2) elevated restarts (needs admin for a routine action); (3) supervisor-owned control: a kill-on-close job, a state file for attestation, a stop-request file.
**Decision:** Option 3. The supervisor puts its wrapper and server in its own kill-on-close job; writes service-<port>.state.json (PIDs, start times, heartbeat every 10 s); stops its own server and exits when stop-<port>.request is newer than its start. Tools that cannot read a command line accept an owner only through a fresh state file (<= 30 s). Stops by name stay forbidden.
**Consequences:** No orphans; the restart script and the gate work for both sessions without elevation; a session-0 owner without a fresh state file is treated as foreign and is never touched. The job, state and stop-request code must not be removed. The reboot test (a25-02) remains user-gated.
**DO NOT re-open** unless a real reboot test shows the S4U chain does not start, or Windows changes job or session-0 access rules.
