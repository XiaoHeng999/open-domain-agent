# sandbox/ — 沙箱执行

- `factory.py` — SandboxFactory + SubprocessSandbox（默认，无隔离）
- `docker.py` — DockerSandbox：容器隔离，支持 snapshot/restore
- `daytona.py` — DaytonaSandbox：Daytona SDK 集成，支持 snapshot/restore
