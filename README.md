# Runnem
**Light-weight service manager for local project development. Makes switching between projects a breeze.**

## Why Runnem?
- **One command to rule them all** – start, stop and inspect every service in your project without memorising half-a-dozen shell scripts.
- **Native speed & tooling** – runs processes directly (no mandatory Docker), leveraging battle-tested GNU screen under the hood.
- **Port-safe project switching** – makes it easy to switch between projects while avoiding port clashes.

## Installation
```bash
pip install runnem   # Python ≥ 3.8 on Linux, macOS or WSL-enabled Windows
```

## Quick start
```bash
# 1 · Create a config for the current directory
runnem init myproject            # omit the name to use the folder name

# 2 · Edit runnem.yaml and add your services
$EDITOR runnem.yaml

# 3 · Launch everything
runnem up                        # starts all services in the right order

# 4 · Check what’s running
runnem list                      # or: runnem ls

# 5 · Stop when you’re done
runnem down                      # stops every service cleanly
```
> **Tip:** Need only one service? Pass its name to up or down, e.g. `runnem up api`.

## Configuration example (`runnem.yaml`)
```yaml
project_name: myproject  # required

services:
  database:
    command: cd database && docker-compose up
    url: postgresql://localhost:5432

  api:
    command: cd api && poetry run uvicorn main:app --reload --port 8000
    url: http://localhost:8000/health
    depends_on: [database]

  frontend:
    command: cd frontend && npm run dev
    url: http://localhost:3000
    depends_on: [api]
```

| Key         | Required | Description |
| ----------- | :------: | ----------- |
| `command`   | ✅        | Shell command executed inside its own screen session. |
| `url`       |          | Health-check endpoint and source of the port number; Runnem waits for it to respond before starting dependants. |
| `depends_on`|          | List of service names that must be running first. |

> Ports are inferred from the `url` – specify one if you want automatic conflict resolution.

## Everyday commands

| Task                  | Command                  |
| --------------------- | ------------------------ |
| Start all services     | `runnem up`               |
| Start one service      | `runnem up <service>`     |
| Stop all services      | `runnem down`             |
| Stop one service       | `runnem down <service>`   |
| Start service + logs   | `runnem run <service>`    |
| Restart service + logs | `runnem rerun <service>`  |
| View live logs         | `runnem log <service>`    |
| List status            | `runnem list` (or `ls`)   |
| Free a busy port       | `runnem kill <port>`      |

## Multiple projects
Runnem looks for the nearest `runnem.yaml` when you run a command.  
If services from another project are still running you’ll see a warning and can stop them with:

```bash
runnem down     # executed from *any* project directory
```

## Contributing
Found a bug, want a feature or to polish the docs? PRs are welcome!

- Fork the repo & `git clone` it.
- `pip install -e .` inside a virtualenv.
- Create a feature branch (`git switch -c my-fix`).
- Commit with clear messages and open a PR.

## License
MIT © 2025 Runnem contributors
