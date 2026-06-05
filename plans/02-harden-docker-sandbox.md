# 02: Harden Docker Sandbox — Close Command Injection Vectors

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening

## What to build

Replace shell-interpolated string commands in `DockerSandbox.exec` with argument lists (`exec_run(cmd=["bash", "-c", command])` or direct list form). Replace heredoc-based `write_file` with tar/archive API (matching existing `read_file` pattern). Ensure command injection payloads via quote escaping return errors instead of executing arbitrary commands.

## Acceptance criteria

- [ ] `DockerSandbox.exec` passes commands as argument lists, not shell-interpolated strings
- [ ] `DockerSandbox.write_file` uses tar/archive API instead of heredoc shell commands
- [ ] Test: command injection payloads (e.g., `'; rm -rf /`) are blocked or escaped, not executed
- [ ] Test: existing sandbox functionality (exec, read_file, write_file) still works correctly

## User stories covered

- US 4: Docker sandbox commands use argument lists, preventing shell injection

## Blocked by

None — can start immediately
