# Mount Log Screen for CLI TUI

Date: 2026-09-15
Status: Approved by product owner

## Problem

Mounting shares from the TUI does not work reliably on Linux: `_plan_mount_linux`
runs `sudo mount ...` via `subprocess.run(capture_output=True)` with no stdin/tty,
so sudo cannot prompt for a password, and the password entered in the modal is
never used for Linux commands (only substituted into the Windows `<PASSWORD>`
placeholder). The only feedback is a transient one-line help-bar message, easy to
miss. The owner wants a simpler, terminal-like mount UX with Ctrl+C abort instead
of modal cancel buttons.

## Design (approved)

### 1. MountLogScreen

New full-screen `MountLogScreen` styled like a terminal:
- top: operation label (e.g. `Mount photos → /mnt/nas/photos`);
- middle: streaming log of command lines and their output;
- bottom: hint `Ctrl+C — cancel`;
- when a command needs a password: an inline line `[sudo] password for <user>:`
  is appended and a single-line hidden input appears; Enter submits, Ctrl+C cancels.

Opened via `push_screen_wait` from `m` / `M` / `u` / `U`.

### 2. Streaming runner

Add a streaming executor in `mount_engine` replacing the silent `capture_output`
path used by the TUI:
- `Popen` with piped stdout/stderr/stdin; lines are forwarded one-by-one to the
  log (a callback / generator), so output appears in real time.
- Linux sudo: run `sudo -S ...` and feed the password via stdin when sudo emits
  the password prompt on stderr (`[sudo] password for ...`). If sudo is cached /
  NOPASSWD, no prompt is shown and no password is needed.
- Windows `net use ... /user:<user> <PASSWORD>`: request the password before
  launch (terminal-style prompt in the log) and substitute it into args.
- Windows junction (`mklink`) needs no password.
- Existing `execute_command` stays for dry-run / non-interactive tests.

### 3. Data flow

- Actions `m`/`M`/`u`/`U` spawn a worker; the worker pushes `MountLogScreen`,
  then walks the selected shares, streaming to the log.
- Per share, a result line is appended: `ok` or the captured error output.
- The log screen owns a `RichLog` widget and a hidden single-line `Input` for the
  password; the worker communicates through the screen object.

### 4. Completion and cancel

- All shares done, no errors, not cancelled → auto-close after a short beat,
  `_do_sync()` runs, table refreshes.
- Errors → log stays open, output visible; any key closes.
- `Ctrl+C` → cancel the batch: terminate the running `Popen`, skip remaining
  shares, log `Cancelled`, close. Binding is screen-level (`ctrl+c`).

## Files touched

- `cli/src/nasmanager/mount_engine.py` — streaming runner (+ keep `execute_command`).
- `cli/src/nasmanager/ui/mountlog.py` (new) — `MountLogScreen`.
- `cli/src/nasmanager/ui/main.py` — actions open the mount log; password asks in-log.
- `cli/tests/test_tui.py` — update `m`-test (PasswordModal → MountLogScreen);
  new tests for streaming runner and cancel.
- `cli/tests/test_mount_engine.py` — tests for the streaming runner.

## Verification

- `just cli-test` green (existing + new tests).
- Headless run: scripted `m` on a NEW share opens MountLogScreen; streaming lines
  appear; Ctrl+C cancels.