"""Task assignment management CLI commands."""

import click
import json
import sys

from workflow.cli.factory import (
    ServiceFactory,
    format_response,
    format_exception,
    dataclass_to_dict,
)


@click.group()
def assignment():
    """タスク割り当て管理コマンド"""
    pass


@assignment.command('assign')
@click.argument('instance_id', type=int)
@click.option('--phase-key', required=True, help='フェーズキー')
@click.option('--specialist', required=True, help='メール or agent_id')
@click.option('--json', 'as_json', is_flag=True, help='JSON形式で出力')
def assign(instance_id: int, phase_key: str, specialist: str, as_json: bool):
    """フェーズに専門家を割り当て（バリデーション）"""
    try:
        factory = ServiceFactory.get_instance()
        assignment_svc = factory.get_assignment_service()
        instance_svc = factory.get_instance_service()

        instance_obj = instance_svc.get_instance(instance_id)

        specialist_id = None
        try:
            specialist_id = int(specialist)
        except ValueError:
            pass

        assignments = {phase_key: specialist_id or specialist}
        resolved = assignment_svc.validate_and_resolve_assignments(
            template_id=instance_obj.template_id,
            assignments=assignments,
        )

        agent = resolved.get(phase_key)

        if as_json:
            response = format_response(
                success=True,
                data={
                    'instance_id': instance_id,
                    'phase_key': phase_key,
                    'specialist': dataclass_to_dict(agent),
                },
            )
            click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            click.echo(
                f"✓ 割り当て確認: {phase_key} → {agent.name} ({agent.email})"
            )

    except Exception as exc:
        error = format_exception(exc)
        if as_json:
            response = format_response(success=False, error=error)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2), err=True)
        else:
            click.echo(f"✗ エラー: {error['message']}", err=True)
        sys.exit(1)


@assignment.command('list-assignments')
@click.argument('instance_id', type=int)
@click.option('--json', 'as_json', is_flag=True, help='JSON形式で出力')
def list_assignments(instance_id: int, as_json: bool):
    """インスタンスの割り当て一覧を表示"""
    try:
        factory = ServiceFactory.get_instance()
        instance_svc = factory.get_instance_service()

        instance_obj = instance_svc.get_instance(instance_id)
        phases = instance_svc.get_instance(instance_id)

        if as_json:
            status_info = instance_svc.get_instance_status(instance_id)
            phases = status_info['phases']
            response = format_response(
                success=True,
                data={
                    'instance_id': instance_id,
                    'phases': [dataclass_to_dict(p) for p in phases],
                },
            )
            click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            status_info = instance_svc.get_instance_status(instance_id)
            phases = status_info['phases']

            click.echo(f"\n👥 インスタンス {instance_id} の割り当て:")
            if not phases:
                click.echo("   割り当てがありません")
                return

            for phase in phases:
                click.echo(f"   • {phase.phase_key}: (フェーズ ID: {phase.phase_id})")

    except Exception as exc:
        error = format_exception(exc)
        if as_json:
            response = format_response(success=False, error=error)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2), err=True)
        else:
            click.echo(f"✗ エラー: {error['message']}", err=True)
        sys.exit(1)


@assignment.command('update-specialist')
@click.argument('instance_id', type=int)
@click.option('--phase-key', required=True, help='フェーズキー')
@click.option('--specialist', required=True, help='新しいメール or agent_id')
@click.option('--json', 'as_json', is_flag=True, help='JSON形式で出力')
def update_specialist(instance_id: int, phase_key: str, specialist: str, as_json: bool):
    """フェーズの専門家を変更"""
    try:
        factory = ServiceFactory.get_instance()
        assignment_svc = factory.get_assignment_service()
        instance_svc = factory.get_instance_service()

        instance_obj = instance_svc.get_instance(instance_id)

        specialist_id = None
        try:
            specialist_id = int(specialist)
        except ValueError:
            pass

        assignments = {phase_key: specialist_id or specialist}
        resolved = assignment_svc.validate_and_resolve_assignments(
            template_id=instance_obj.template_id,
            assignments=assignments,
        )

        agent = resolved.get(phase_key)

        if as_json:
            response = format_response(
                success=True,
                data={
                    'instance_id': instance_id,
                    'phase_key': phase_key,
                    'new_specialist': dataclass_to_dict(agent),
                },
            )
            click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            click.echo(
                f"✓ 専門家変更: {phase_key} → {agent.name} ({agent.email})"
            )

    except Exception as exc:
        error = format_exception(exc)
        if as_json:
            response = format_response(success=False, error=error)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2), err=True)
        else:
            click.echo(f"✗ エラー: {error['message']}", err=True)
        sys.exit(1)
