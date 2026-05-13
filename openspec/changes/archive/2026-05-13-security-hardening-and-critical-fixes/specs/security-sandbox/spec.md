## MODIFIED Requirements

### Requirement: Human-in-the-Loop Layered Approval
The whitelist-based command safety checker MUST use shell-aware parsing that detects dangerous shell metacharacters (`;`, `|`, `$()`, `&&`, backticks) rather than only inspecting the first space-delimited token. Compound commands containing dangerous metacharacters MUST be rejected outright. Additionally, the checker MUST handle bash encoding tricks (`$'\x72\x6d'`), quote context (`"; "` inside quoted strings is not a command separator), and MUST NOT classify `||` as a "low-risk pipe" — it MUST be classified as an OR operator with its own risk category.

#### Scenario: Bash encoding bypass attempt
- **WHEN** command contains `$'\x72\x6d'` encoded characters
- **THEN** the checker decodes and evaluates the actual command, blocking if dangerous

#### Scenario: Quoted semicolon is safe
- **WHEN** command is `echo "hello; world"`
- **THEN** the checker recognizes the semicolon is inside quotes and does NOT block

#### Scenario: OR operator not confused with pipe
- **WHEN** command is `false || cat /etc/passwd`
- **THEN** `||` is classified as OR operator (not pipe), and the command is blocked

### Requirement: SSRF DNS Resolution Check
`SSRFProtector.check_url()` MUST perform DNS resolution after hostname validation and verify ALL resolved IP addresses against `_PRIVATE_NETWORKS`. The previously-deferred `check_resolved_ip()` MUST be integrated into the standard `check_url` flow.

#### Scenario: Domain resolves to private IP
- **WHEN** URL hostname is `evil.internal` which resolves to `127.0.0.1`
- **THEN** check_url returns `safe=False` with reason indicating DNS rebinding detected

#### Scenario: Domain resolves to public IP
- **WHEN** URL hostname is `example.com` which resolves to `93.184.216.34`
- **THEN** check_url returns `safe=True`

#### Scenario: Domain with multiple IPs, one private
- **WHEN** URL hostname resolves to both a public and a private IP
- **THEN** check_url returns `safe=False` (any private IP is blocked)

## ADDED Requirements

### Requirement: Non-standard IP representation handling
`SSRFProtector.check_url()` MUST detect and normalize non-standard IP representations before validation. This includes decimal (`2130706433`), hexadecimal (`0x7f000001`), octal (`017700000001`), and IPv4-mapped IPv6 (`::ffff:127.0.0.1`) formats. URLs using these representations targeting private networks MUST be blocked.

#### Scenario: Decimal IP blocked
- **WHEN** URL is `http://2130706433/` (equivalent to 127.0.0.1)
- **THEN** check_url returns `safe=False`

#### Scenario: Hexadecimal IP blocked
- **WHEN** URL is `http://0x7f000001/` (equivalent to 127.0.0.1)
- **THEN** check_url returns `safe=False`

#### Scenario: IPv4-mapped IPv6 blocked
- **WHEN** URL contains `::ffff:127.0.0.1`
- **THEN** check_url returns `safe=False`

#### Scenario: Octal IP blocked
- **WHEN** URL is `http://017700000001/` (equivalent to 127.0.0.1)
- **THEN** check_url returns `safe=False`

### Requirement: Trailing dot hostname matching
`_BLOCKED_HOSTS` matching MUST handle hostnames with trailing dots (e.g., `metadata.google.internal.`). The comparison MUST strip trailing dots before matching.

#### Scenario: Blocked host with trailing dot
- **WHEN** URL hostname is `metadata.google.internal.` (with trailing dot)
- **THEN** check_url returns `safe=False` (matches `metadata.google.internal`)

### Requirement: Docker sandbox command escaping
`DockerSandbox.exec()` MUST use `shlex.quote()` to escape the command string before embedding it in `bash -c`. `DockerSandbox.write_file()` MUST use `shlex.quote()` for the path argument and MUST transmit file content via a Python one-liner reading from stdin (or base64 encoding), not via heredoc.

#### Scenario: Command with single quote
- **WHEN** exec() is called with command `echo 'hello'`
- **THEN** the command is safely escaped and executed in the container without shell injection

#### Scenario: Write file with heredoc-terminating content
- **WHEN** write_file() is called with content containing the string "ENDOFFILE"
- **THEN** the file is written correctly without premature termination

### Requirement: SubprocessSandbox path validation
`SubprocessSandbox` MUST validate all file paths against a configured workspace directory using `Path.resolve()` + `is_relative_to()`. Commands MUST be executed via `shlex.split()` + `create_subprocess_exec` (not `create_subprocess_shell`) when possible.

#### Scenario: Path traversal in read_file
- **WHEN** SubprocessSandbox.read_file() receives path `../../etc/passwd`
- **THEN** the operation is rejected with a security error

#### Scenario: Command without shell metacharacters
- **WHEN** SubprocessSandbox.exec() receives a simple command like `ls -la /workspace`
- **THEN** the command is split via shlex.split() and executed via create_subprocess_exec (no shell)
