## MODIFIED Requirements

### Requirement: Filesystem Workspace Restriction
All filesystem tools MUST enforce workspace boundary checking using `Path.resolve()` (which resolves symlinks) and `Path.is_relative_to()` (which prevents boundary bugs like `/data/app` matching `/data/application`). The SafetyManager MUST reject any path that resolves outside the configured workspace, including paths that traverse through symlinks pointing outside the workspace.

#### Scenario: Symlink pointing outside workspace
- **WHEN** a symlink inside `/workspace` points to `/etc/passwd`
- **THEN** read_file on that symlink path returns a security error

#### Scenario: Similar-prefix path rejected
- **WHEN** workspace is `/data/app` and path is `/data/application/secret`
- **THEN** the operation is rejected (not falsely matched by startswith)

#### Scenario: Normal path within workspace
- **WHEN** workspace is `/data/app` and path is `/data/app/src/main.py`
- **THEN** the operation proceeds normally
