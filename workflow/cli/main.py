"""Main CLI entry point."""

import click
import json
import sys

from workflow.cli.factory import ServiceFactory, format_response, format_exception


@click.group()
@click.version_option()
def cli():
    """AI Orchestrator CLI - ワークフローテンプレート管理システム"""
    pass


def load_cli_commands():
    from workflow.cli.template import template
    from workflow.cli.instance import instance
    from workflow.cli.assignment import assignment

    cli.add_command(template)
    cli.add_command(instance)
    cli.add_command(assignment)


if __name__ == '__main__':
    load_cli_commands()
    cli()
