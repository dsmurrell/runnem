"""Core functionality for the runnem service manager."""

import os
import subprocess
import time
import warnings
import gzip
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import urllib3
import yaml

warnings.filterwarnings(
    "ignore",
    message="Unverified HTTPS request",
    category=urllib3.exceptions.InsecureRequestWarning,
)

SCREEN_PREFIX = "runnem"
CONFIG_FILE = "runnem.yaml"
MAX_DEPENDENCY_RETRIES = 3
DEPENDENCY_RETRY_DELAY = 2

# Logging configuration
RUNNEM_HOME = Path(os.getenv("RUNNEM_HOME", Path.home() / ".runnem"))
LOG_MAX_BYTES = 100 * 1024 * 1024  # 100 MB per service
LOG_BACKUPS = 3  # keep last 3 compressed archives


def get_log_dir(project_name: str) -> Path:
    """Get the log directory for a project."""
    log_dir = RUNNEM_HOME / "logs" / project_name
    log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    return log_dir


def get_log_path(project_name: str, service_name: str) -> Path:
    """Get the log file path for a service."""
    return get_log_dir(project_name) / f"{service_name}.log"


def rotate_log(log_path: Path) -> None:
    """Rotate a log file if it exceeds the maximum size."""
    if not log_path.exists() or log_path.stat().st_size < LOG_MAX_BYTES:
        return

    # Create timestamped archive
    ts = time.strftime("%Y%m%d-%H%M%S")
    archive = log_path.with_suffix(f".{ts}.gz")
    with open(log_path, "rb") as src, gzip.open(archive, "wb") as dst:
        shutil.copyfileobj(src, dst)
    log_path.unlink()  # start fresh

    # Prune old archives
    archives = sorted(log_path.parent.glob(f"{log_path.stem}.*.gz"))
    for old in archives[:-LOG_BACKUPS]:
        old.unlink(missing_ok=True)


def build_dependency_graph(config: Dict) -> Dict[str, List[str]]:
    """Build a graph of service dependencies."""
    graph = {}
    for service_name, service_config in config.get("services", {}).items():
        graph[service_name] = service_config.get("depends_on", [])
    return graph


def detect_cycles(graph: Dict[str, List[str]]) -> Optional[List[str]]:
    """Detect cycles in the dependency graph. Returns the cycle if found, None otherwise."""
    visited = set()
    path = []
    path_set = set()

    def visit(node: str) -> Optional[List[str]]:
        if node in path_set:
            start = path.index(node)
            return path[start:] + [node]
        if node in visited:
            return None

        visited.add(node)
        path.append(node)
        path_set.add(node)

        for neighbor in graph.get(node, []):
            cycle = visit(neighbor)
            if cycle:
                return cycle

        path.pop()
        path_set.remove(node)
        return None

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def topological_sort(graph: Dict[str, List[str]]) -> List[str]:
    """Sort services by dependency order."""
    in_degree = defaultdict(int)
    for node in graph:
        for dep in graph[node]:
            in_degree[dep] += 1

    # Start with nodes that have no dependencies
    queue = [node for node in graph if in_degree[node] == 0]
    result = []

    while queue:
        node = queue.pop(0)
        result.append(node)

        # For each node that depends on this one
        for service, deps in graph.items():
            if node in deps:
                in_degree[service] -= 1
                if in_degree[service] == 0:
                    queue.append(service)

    return result


def wait_for_service(name: str, config: Dict) -> bool:
    """Wait for a service to be available by checking its URL."""
    service_config = config.get("services", {}).get(name, {})
    url = service_config.get("url", "")
    if not url:
        return True  # No URL to check

    for attempt in range(MAX_DEPENDENCY_RETRIES):
        try:
            response = requests.get(url, timeout=5, verify=False)
            if response.status_code < 500:  # Accept any non-server error response
                return True
        except requests.RequestException:
            pass

        if attempt < MAX_DEPENDENCY_RETRIES - 1:
            print(f"⏳ Waiting for {name} to be ready...")
            time.sleep(DEPENDENCY_RETRY_DELAY)

    return False


def find_project_config() -> Optional[Tuple[str, Dict]]:
    """Find and load the nearest runnem.yaml file, searching up through parent directories.
    Returns a tuple of (project_name, config) if found, None otherwise."""
    current_dir = Path.cwd()
    while current_dir != current_dir.parent:
        config_path = current_dir / CONFIG_FILE
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
                if not isinstance(config, dict) or "project_name" not in config:
                    print(f"⚠️ Invalid config file at {config_path}: missing project_name")
                    return None
                return config["project_name"], config
        current_dir = current_dir.parent
    return None


def get_project_name() -> Optional[str]:
    """Get the project name from the nearest runnem.yaml file."""
    result = find_project_config()
    return result[0] if result else None


def get_project_config(project_name: str) -> Dict:
    """Load project configuration from YAML file."""
    result = find_project_config()
    if not result:
        raise FileNotFoundError("Project configuration not found. Run 'runnem init <project_name>' first.")

    config_name, config = result
    if config_name != project_name:
        raise FileNotFoundError(f"Project '{project_name}' not found. Found project '{config_name}' instead.")

    return config


def get_screen_name(project_name: str, service_name: str) -> str:
    """Get the screen session name for a service."""
    return f"{SCREEN_PREFIX}-{project_name}-{service_name}"


def is_service_running(project_name: str, name: str) -> bool:
    """Check if a service is already running."""
    screen_name = get_screen_name(project_name, name)
    result = subprocess.run("screen -ls", shell=True, capture_output=True, text=True)

    # More robust check for screen session existence
    # Look for either ".<screen_name>" pattern or directly for screen_name
    return f".{screen_name}" in result.stdout or f"{screen_name}" in result.stdout


def get_service_port(name: str, config: Dict) -> Optional[int]:
    """Get the port number from the service configuration."""
    service_config = config.get("services", {}).get(name, {})
    url = service_config.get("url", "")
    if not url:
        return None
    # Extract port from URL, handling both http and https
    try:
        return int(url.split(":")[-1].split("/")[0])
    except (ValueError, IndexError):
        return None


def check_port_conflict(port: int) -> bool:
    """Check if a port is in use and return True if there's a conflict."""
    try:
        result = subprocess.run(
            f"lsof -i :{port}",
            shell=True,
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
    except subprocess.SubprocessError:
        return False


def kill_port_process(port: int) -> bool:
    """Kill any process using the specified port."""
    try:
        # First get all PIDs using the port (including those just bound to it)
        result = subprocess.run(
            f"lsof -i :{port} -t",  # -t outputs only the PIDs
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                # Redirect stderr to /dev/null to suppress "No such process" messages
                subprocess.run(f"kill -9 {pid} 2>/dev/null", shell=True, check=False)
            return True
    except subprocess.SubprocessError:
        pass
    return False


def check_service_status(project_name: str, name: str, config: Dict) -> bool:
    """Check if a service started successfully and show appropriate message."""
    if not is_service_running(project_name, name):
        print(f"❌ Failed to start {name}, try running the service directly to see what's happening.")
        print("―" * 40)

        # Try to read logs from the log file
        log_path = get_log_path(project_name, name)
        if log_path.exists():
            with open(log_path) as f:
                print(f.read())
        else:
            print("No logs available. The service may have failed to start correctly.")

        print("―" * 40)

        # Clean up any leftover processes
        port = get_service_port(name, config)
        if port and kill_port_process(port):
            print(f"🧹 Cleaned up processes using port {port}")

        return False
    else:
        status_msg = f"✅ Started {name}"
        service_config = config.get("services", {}).get(name, {})
        url = service_config.get("url")
        if url:
            status_msg += f"   📎 {url}"
        log_path = get_log_path(project_name, name)
        status_msg += f"   📝 {log_path}"
        print(status_msg)
        return True


def start_service_async(project_name: str, name: str, command: str, show_status: bool = True) -> bool:
    """Start a service asynchronously and optionally show its status."""
    if is_service_running(project_name, name):
        if show_status:
            print(f"⚠️ {name} is already running.")
        return True

    if show_status:
        print(f"🚀 Starting {name}...")

    # Set up logging
    log_path = get_log_path(project_name, name)
    rotate_log(log_path)  # Archive if the previous run got too big

    # Wrap the command to capture stderr and stdout to both the screen and the log file
    wrapped_command = f"({command}) 2>&1 | tee -a {log_path}"

    screen_name = get_screen_name(project_name, name)
    subprocess.run(
        f"screen -L -Logfile {log_path} -dmS {screen_name} bash -c '{wrapped_command}'",
        shell=True,
        check=False,
    )

    # Wait a brief moment to ensure the command has a chance to start and output initial logs
    time.sleep(0.1)

    return True


def check_and_clear_port(name: str, config: Dict) -> bool:
    """Check if a service's port is in use and clear it if necessary.
    Returns True if the port is available (either naturally or after clearing)."""
    port = get_service_port(name, config)
    if port:
        # Try to kill any process using the port
        if kill_port_process(port):
            print(f"\n⚠️ Port {port} was in use.")
            print(f"🧹 Cleaned up port {port} for {name}")
    return True  # Always return True since we either cleaned it or it wasn't in use


def start_service(name: str, config: Dict) -> None:
    """Start a service if it's not already running."""
    project_name = config.get("project_name")
    service_config = config.get("services", {}).get(name)
    if not service_config:
        print(f"❌ Unknown service: {name}")
        return

    # Check if the service is already running in the current project
    if is_service_running(project_name, name):
        print(f"⚠️ {name} is already running in project '{project_name}'.")
        return

    # Check and clear port before starting
    if not check_and_clear_port(name, config):
        print("❌ Service not started.")
        return

    if start_service_async(project_name, name, service_config["command"]):
        # Give the service a moment to start (reduced to speed up startup)
        time.sleep(0.1)
        check_service_status(project_name, name, config)


def list_services() -> None:
    """List all running services."""
    result = subprocess.run("screen -ls", shell=True, capture_output=True, text=True)
    running_services = [line for line in result.stdout.split("\n") if SCREEN_PREFIX in line]

    if running_services:
        print("\n🟢 Running Services:")
        for service in running_services:
            print(f" - {service.strip()}")
    else:
        print("⚠️ No services running.")


def _inject_detach_hint(screen_name: str) -> None:
    """Write a one-off hint into the screen window itself."""
    hint = "--- (runnem)  Detach with Ctrl+A then still holding Ctrl, press D ---\n"
    # Add the hint without clearing the screen
    subprocess.run(
        f"screen -S {screen_name} -X stuff '{hint}'",
        shell=True,
        check=False,
    )
    # Force a redraw
    subprocess.run(
        f"screen -S {screen_name} -X redraw",
        shell=True,
        check=False,
    )


def view_logs(name: str, config: Dict) -> None:
    """View logs for a service."""
    project_name = config.get("project_name")
    if not is_service_running(project_name, name):
        print(f"⚠️ {name} is not running.")
        # Try to retrieve logs from the log file
        log_path = get_log_path(project_name, name)
        if log_path.exists():
            print("\nLast known logs:")
            print("―" * 40)
            with open(log_path) as f:
                print(f.read())
            print("―" * 40)
        else:
            print("No logs available for this service.")
        return

    screen_name = get_screen_name(project_name, name)
    # _inject_detach_hint(screen_name) // removed for now as it inserts this what should be user feedback straight into any inputs that the program is requiring from the user.
    os.system(f"screen -r {screen_name}")


def list_all_services(config: Dict) -> None:
    """List all services and their status."""
    project_name = config.get("project_name")
    print("\n📋 Services Status:")
    services = list(config.get("services", {}).keys())
    for service_name in services:
        status = "🟢 Running" if is_service_running(project_name, service_name) else "⚫️ Stopped"
        service_config = config.get("services", {}).get(service_name, {})
        url = service_config.get("url", "")
        print(f"\n - {service_name}: {status}")
        if url and is_service_running(project_name, service_name):
            print(f"   📎 {url}")
    print()


def start_all_services(config: Dict) -> None:
    """Start all services asynchronously while respecting dependencies."""
    project_name = config.get("project_name")
    # Build dependency graph
    graph = build_dependency_graph(config)

    # Check for circular dependencies
    cycle = detect_cycles(graph)
    if cycle:
        print("❌ Circular dependency detected:")
        print(" → ".join(cycle))
        return

    # First identify which services need to be started
    all_services = list(config.get("services", {}).keys())
    services_to_start = [name for name in all_services if not is_service_running(project_name, name)]

    if not services_to_start:
        print("✨ All services are already running!")
        return

    # Check ports only for services that need to be started
    print("\n🔍 Checking ports...")
    for name in services_to_start:
        if not check_and_clear_port(name, config):
            print("❌ Aborting startup due to port conflicts.")
            return

    # Group services by their dependency requirements
    services_with_deps = {name for name, deps in graph.items() if deps}
    independent_services = set(graph.keys()) - services_with_deps

    # Start all independent services asynchronously first
    print("\n🔄 Starting independent services...\n")

    # First, start all independent services in parallel without waiting for status
    started_services = []
    for name in independent_services:
        if name not in services_to_start:
            continue
        service_config = config["services"][name]
        if start_service_async(project_name, name, service_config["command"], show_status=True):
            started_services.append(name)

    # Give services a brief moment to initialize
    if started_services:
        time.sleep(0.2)
        print("")  # Add a blank line to separate launches from statuses

    # Then check their status
    for name in started_services:
        check_service_status(project_name, name, config)

    # Wait a moment to catch any immediate failures
    print("\n⏳ Checking service health...")
    time.sleep(2)  # Give services a moment to start and potentially fail

    # Check status again to catch any immediate failures
    any_failures = False
    for name in started_services:
        if not is_service_running(project_name, name):
            any_failures = True
            # Only show status for failed services
            check_service_status(project_name, name, config)

    if any_failures:
        print("\n⚠️ Some services failed to start properly. Check the logs with 'runnem log <service>' for details.")
        return

    # Start dependent services after checking their dependencies
    if services_with_deps:
        print("\n🔄 Starting dependent services...")
        for name in services_with_deps:
            if name not in services_to_start:
                continue
            deps = graph[name]
            print(f"\n📦 Checking dependencies for {name}...")

            # Check if dependencies are running and ready
            deps_ready = True
            for dep in deps:
                if not is_service_running(project_name, dep):
                    print(f"❌ Dependency {dep} is not running")
                    deps_ready = False
                    break
                print(f"⏳ Waiting for {dep} to be ready...")
                if not wait_for_service(dep, config):
                    print(f"❌ Dependency {dep} is not responding")
                    deps_ready = False
                    break
                print(f"✅ {dep} is ready")

            if deps_ready:
                service_config = config["services"][name]
                if start_service_async(project_name, name, service_config["command"], show_status=True):
                    # Brief wait to allow service to initialize
                    time.sleep(0.2)
                    print("")  # Add a blank line to separate launch from status
                    check_service_status(project_name, name, config)
                else:
                    print(f"❌ Failed to start {name}, try running the service directly to see what's happening.")
                    return

    print("\n✨ All services started!")


def init_project(project_name: str = None) -> None:
    """Initialize a new project configuration."""
    # Create config file in current directory
    config_path = Path.cwd() / CONFIG_FILE
    if config_path.exists():
        print(f"⚠️ Project configuration already exists at {config_path}")
        return

    # Use current directory name if no project name provided
    if project_name is None:
        project_name = Path.cwd().name

    # Get the template path relative to this file
    template_path = Path(__file__).parent / "template.yaml"

    # Read and format the template
    with open(template_path) as f:
        config_content = f.read().format(project_name=project_name)

    # Write the config file
    with open(config_path, "w") as f:
        f.write(config_content)

    print(f"✨ Initialized project {project_name}")
    print(f"📝 Edit {config_path} to configure your services")


def get_running_screen_sessions() -> List[str]:
    """Get all running screen sessions that start with the runnem prefix."""
    result = subprocess.run("screen -ls", shell=True, capture_output=True, text=True)
    return [line.strip() for line in result.stdout.split("\n") if SCREEN_PREFIX in line and line.strip()]


def get_other_project_services(current_project: str) -> List[str]:
    """Get list of running services from other projects."""
    sessions = get_running_screen_sessions()
    other_services = []

    expected_prefix = f"{SCREEN_PREFIX}-{current_project}"
    for session in sessions:
        # Screen output format is like: "8261.runnem-project-name-server\t(Detached)"
        screen_name = session.split("\t")[0].split(".")[-1]  # Get "runnem-project-name-server"
        # If it's a runnem service but doesn't have our project prefix, it's from another project
        if screen_name.startswith(f"{SCREEN_PREFIX}-") and not screen_name.startswith(expected_prefix):
            other_services.append(session)

    return other_services


def stop_all_running_services() -> None:
    """Stop all running runnem services regardless of project."""
    sessions = get_running_screen_sessions()

    if not sessions:
        print("⚠️ No services running.")
        return

    # First, collect all the services we need to stop
    services_to_stop = []
    for session in sessions:
        # Screen output format is like: "8261.runnem-project-name-server\t(Detached)"
        screen_name = session.split("\t")[0].split(".")[-1]  # Get "runnem-project-name-server"
        if not screen_name.startswith(f"{SCREEN_PREFIX}-"):
            continue

        # Get everything after runnem- as the service identifier
        prefix_len = len(f"{SCREEN_PREFIX}-")
        service_id = screen_name[prefix_len:]  # Remove prefix
        # Split on the last hyphen to separate project and service
        parts = service_id.rsplit("-", 1)
        if len(parts) != 2:  # Need both project and service
            continue

        project, service = parts
        services_to_stop.append({"screen_name": screen_name, "project": project, "service": service})

    # Then stop each service
    for service in services_to_stop:
        # Wrap all screen commands in a subshell and redirect all output
        subprocess.run(
            f"( screen -S {service['screen_name']} -X stuff $'\\003' && sleep 0.5 && screen -S {service['screen_name']} -X kill && sleep 0.1 && screen -X -S {service['screen_name']} quit ) >/dev/null 2>&1",
            shell=True,
            check=False,
        )
        print(f"🛑 Stopped {service['service']} (from project '{service['project']}')")


def check_other_projects(current_project: str) -> bool:
    """Check if there are services running from other projects.
    Returns True if other projects are running, False otherwise."""
    other_services = get_other_project_services(current_project)

    if other_services:
        print("\n⚠️ Found running services from other projects:\n")
        for session in other_services:
            # Screen output format is like: "8261.runnem-project-name-server\t(Detached)"
            screen_name = session.split("\t")[0].split(".")[-1]  # Get "runnem-project-name-server"
            # Get everything after runnem- as the service identifier
            prefix_len = len(f"{SCREEN_PREFIX}-")
            service_id = screen_name[prefix_len:]  # Remove prefix
            # Split on the last hyphen to separate project and service
            project, service = service_id.rsplit("-", 1)
            print(f" - {service} (from project '{project}')")
        print("\nYou must stop all services from other projects before using runnem here.")
        print("Run 'runnem down' to stop all services.")
        return True

    return False


def stop_service(name: str, config: Dict) -> None:
    """Stop a running service and cleanup any leftover processes."""
    project_name = config.get("project_name")
    if not is_service_running(project_name, name):
        print(f"⚠️ {name} is not running.")
        # Still try to cleanup any leftover processes
        port = get_service_port(name, config)
        if port and kill_port_process(port):
            print(f"🧹 Cleaned up processes using port {port}")
        return

    screen_name = get_screen_name(project_name, name)

    # Wrap all screen commands in a subshell and redirect all output
    subprocess.run(
        f"( screen -S {screen_name} -X stuff $'\\003' && sleep 0.5 && screen -S {screen_name} -X kill && sleep 0.1 && screen -X -S {screen_name} quit ) >/dev/null 2>&1",
        shell=True,
        check=False,
    )

    # Then ensure the port is free
    port = get_service_port(name, config)
    if port and kill_port_process(port):
        print(f"🧹 Cleaned up processes using port {port}")

    print("🛑 Stopped " + name)
