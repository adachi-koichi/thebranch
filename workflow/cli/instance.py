"""Workflow instance management CLI commands."""

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
def instance():
    """ワークフローインスタンス管理コマンド"""
    pass


@instance.command('instantiate')
@click.argument('template_id', type=int)
@click.option('--name', required=True, help='インスタンス名')
@click.option(
    '--assignments',
    required=True,
    type=str,
    help='JSON形式の割り当て辞書 例: {"phase1": "alice@example.com"}',
)
@click.option('--context', type=str, default='{}', help='カスタムコンテキスト（JSON）')
@click.option('--json', 'as_json', is_flag=True, help='JSON形式で出力')
def instantiate(
    template_id: int,
    name: str,
    assignments: str,
    context: str,
    as_json: bool,
):
    """テンプレートをワークフローインスタンスに変換"""
    try:
        assignments_dict = json.loads(assignments)
        context_dict = json.loads(context)

        factory = ServiceFactory.get_instance()
        svc = factory.get_instance_service()
        instance_obj = svc.instantiate_workflow(
            template_id=template_id,
            instance_name=name,
            specialist_assignments=assignments_dict,
            context=context_dict,
        )

        if as_json:
            response = format_response(
                success=True,
                data=dataclass_to_dict(instance_obj),
            )
            click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            click.echo(
                f"✓ インスタンス作成成功: {instance_obj.name} (ID: {instance_obj.id})"
            )
            click.echo(f"  ステータス: {instance_obj.status}")

    except json.JSONDecodeError as e:
        error = {'type': 'JSONDecodeError', 'message': f'JSON解析エラー: {str(e)}', 'details': {}}
        if as_json:
            response = format_response(success=False, error=error)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2), err=True)
        else:
            click.echo(f"✗ エラー: {error['message']}", err=True)
        sys.exit(1)

    except Exception as exc:
        error = format_exception(exc)
        if as_json:
            response = format_response(success=False, error=error)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2), err=True)
        else:
            click.echo(f"✗ エラー: {error['message']}", err=True)
        sys.exit(1)


@instance.command('status')
@click.argument('instance_id', type=int)
@click.option('--json', 'as_json', is_flag=True, help='JSON形式で出力')
def status(instance_id: int, as_json: bool):
    """ワークフローインスタンスのステータスを表示"""
    try:
        factory = ServiceFactory.get_instance()
        svc = factory.get_instance_service()
        status_info = svc.get_instance_status(instance_id)

        if as_json:
            data = {
                'instance': dataclass_to_dict(status_info['instance']),
                'phases': [dataclass_to_dict(p) for p in status_info['phases']],
                'tasks': [dataclass_to_dict(t) for t in status_info['tasks']],
                'progress': status_info['progress'],
            }
            response = format_response(success=True, data=data)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            instance_obj = status_info['instance']
            progress = status_info['progress']

            click.echo(f"\n🔄 ワークフローステータス")
            click.echo(f"   ID: {instance_obj.id}")
            click.echo(f"   名前: {instance_obj.name}")
            click.echo(f"   ステータス: {instance_obj.status}")
            click.echo(
                f"   進捗: {progress['completed']}/{progress['total']} "
                f"({progress['pct']}%)"
            )

            phases = status_info['phases']
            if phases:
                click.echo(f"\n   フェーズ:")
                for phase in phases:
                    phase_status = (
                        '⏳' if phase.status == 'waiting'
                        else '▶' if phase.status == 'ready'
                        else '▶▶' if phase.status == 'running'
                        else '✓'
                    )
                    click.echo(f"     {phase_status} {phase.phase_key}: {phase.status}")

    except Exception as exc:
        error = format_exception(exc)
        if as_json:
            response = format_response(success=False, error=error)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2), err=True)
        else:
            click.echo(f"✗ エラー: {error['message']}", err=True)
        sys.exit(1)


@instance.command('execute')
@click.argument('instance_id', type=int)
@click.option('--phase-key', default=None, help='進行させるフェーズキー（指定時）')
@click.option('--json', 'as_json', is_flag=True, help='JSON形式で出力')
def execute(instance_id: int, phase_key: str | None, as_json: bool):
    """ワークフロー実行を開始 / フェーズを進行"""
    try:
        factory = ServiceFactory.get_instance()
        svc = factory.get_instance_service()

        if phase_key:
            phase_instance = svc.advance_phase(instance_id, phase_key)

            if as_json:
                response = format_response(
                    success=True,
                    data=dataclass_to_dict(phase_instance),
                )
                click.echo(json.dumps(response, ensure_ascii=False, indent=2))
            else:
                click.echo(f"✓ フェーズ進行: {phase_instance.phase_key} → {phase_instance.status}")
        else:
            instance_obj = svc.get_instance(instance_id)

            if as_json:
                response = format_response(
                    success=True,
                    data=dataclass_to_dict(instance_obj),
                )
                click.echo(json.dumps(response, ensure_ascii=False, indent=2))
            else:
                click.echo(f"✓ インスタンス実行: {instance_obj.name} (ID: {instance_obj.id})")

    except Exception as exc:
        error = format_exception(exc)
        if as_json:
            response = format_response(success=False, error=error)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2), err=True)
        else:
            click.echo(f"✗ エラー: {error['message']}", err=True)
        sys.exit(1)
