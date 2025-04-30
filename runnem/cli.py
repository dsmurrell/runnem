"""Command-line interface for runnem."""

import click
from importlib.metadata import version

from .core import (
    check_other_projects,
    check_port_conflict,
    get_project_config,
    get_project_name,
    init_project,
    kill_port_process,
    list_all_services,
    start_all_services,
    start_service,
    stop_all_running_services,
    stop_service,
    view_logs,
)


@click.group(
    epilog="""
Examples:

    $ runnem init myproject

    $ runnem up

    $ runnem up frontend

    $ runnem down

    $ runnem down backend

    $ runnem list

    $ runnem ls

    $ runnem log frontend

    $ runnem kill 3000
"""
)
@click.version_option(version=version("runnem"), message="runnem version %(version)s")
def main():
    """runnem - A service manager for managing multiple services in a project."""
    pass


@main.command()
@click.argument("project_name", required=False)
def init(project_name):
    """Initialize a new project configuration."""
    init_project(project_name)


@main.command()
@click.argument("service", required=False)
def up(service):
    """Start all services, or a specific service if specified."""
    project_name = get_project_name()
    if not project_name:
        click.echo("❌ No project found. Run 'runnem init <project_name>' first.")
        return

    # Check for other project services before doing anything else
    if check_other_projects(project_name):
        raise click.Abort()

    try:
        config = get_project_config(project_name)
        if service is None:
            start_all_services(config)
        else:
            start_service(service, config)
    except FileNotFoundError as e:
        click.echo(f"❌ {e}")
        return


@main.command()
@click.argument("service", required=False)
def down(service):
    """Stop all services, or a specific service if specified."""
    if service is None:
        # If no service specified, stop all running services from any project
        stop_all_running_services()
        return

    # If a specific service is specified, we need the project config
    project_name = get_project_name()
    if not project_name:
        click.echo("❌ No project found. Run 'runnem init <project_name>' first.")
        return

    try:
        config = get_project_config(project_name)
        stop_service(service, config)
    except FileNotFoundError as e:
        click.echo(f"❌ {e}")
        return


@main.command()
def list():
    """List all services and their status."""
    project_name = get_project_name()
    if not project_name:
        click.echo("❌ No project found. Run 'runnem init <project_name>' first.")
        return

    # Check for other project services before doing anything else
    if check_other_projects(project_name):
        return

    try:
        config = get_project_config(project_name)
        list_all_services(config)
    except FileNotFoundError as e:
        click.echo(f"❌ {e}")
        return


@main.command(name="ls", help="List all services and their status.")
def list_alias():
    """Alias for 'list' command."""
    project_name = get_project_name()
    if not project_name:
        click.echo("❌ No project found. Run 'runnem init <project_name>' first.")
        return

    # Check for other project services before doing anything else
    if check_other_projects(project_name):
        return

    try:
        config = get_project_config(project_name)
        list_all_services(config)
    except FileNotFoundError as e:
        click.echo(f"❌ {e}")
        return


@main.command()
@click.argument("service")
def log(service):
    """View logs for a service."""
    project_name = get_project_name()
    if not project_name:
        click.echo("❌ No project found. Run 'runnem init <project_name>' first.")
        return

    # Check for other project services before doing anything else
    if check_other_projects(project_name):
        return

    try:
        config = get_project_config(project_name)
        if service not in config.get("services", {}):
            click.echo(f"❌ Unknown service: {service}")
            return
        view_logs(service, config)
    except FileNotFoundError as e:
        click.echo(f"❌ {e}")
        return


@main.command()
@click.argument("port", type=int)
def kill(port):
    """Kill any process running on the specified port."""
    if not check_port_conflict(port):
        click.echo(f"⚠️ No process found on port {port}")
        return

    if kill_port_process(port):
        click.echo(f"🧹 Cleaned up processes using port {port}")
    else:
        click.echo(f"❌ Failed to kill process on port {port}")


if __name__ == "__main__":
    main()
