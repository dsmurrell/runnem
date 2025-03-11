# runnem

A service manager for managing multiple services in a project. runnem helps you manage and run multiple services in your project with a simple CLI interface.

## Installation

```bash
pip install runnem
```

## Usage

### Initialize a Project

```bash
runnem init myproject
```

This will:
1. Create a new project configuration in `~/.runnem/myproject.yaml`
2. Create a `.runnem` file in the current directory with the project name

### Manage Services

```bash
# Start all services
runnem up all

# Start a specific service
runnem up api

# Stop all services
runnem down all

# Stop a specific service
runnem down api

# List running services
runnem list

# View service logs
runnem log api
```

## Project Configuration

Each project has its own YAML configuration file stored in `~/.runnem/{project}.yaml`. Here's an example configuration:

```yaml
services:
  app:
    command: "cd ~/projects/myproject/app && npm run dev"
    port: 3000
    url: "http://localhost:3000"
  api:
    command: "cd ~/projects/myproject/api && python run.py"
    port: 8000
    url: "http://localhost:8000"
```

## Auto-Detection

runnem automatically detects the project you're working on by looking for a `.runnem` file in the current directory or any parent directory. This means you can run runnem commands from anywhere inside your project.

## License

MIT License