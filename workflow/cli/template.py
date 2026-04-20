"""Template management CLI commands."""

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
def template():
    """テンプレート管理コマンド"""
    pass


@template.command('create')
@click.option('--name', required=True, help='テンプレート名')
@click.option('--description', default=None, help='テンプレート説明')
@click.option('--created-by', default=None, help='作成者（email or agent_id）')
@click.option('--json', 'as_json', is_flag=True, help='JSON形式で出力')
def create(name: str, description: str | None, created_by: str | None, as_json: bool):
    """新規テンプレートを作成"""
    try:
        factory = ServiceFactory.get_instance()
        svc = factory.get_template_service()
        template_obj = svc.create_template(
            name=name,
            description=description,
            created_by=created_by,
        )

        if as_json:
            response = format_response(
                success=True,
                data=dataclass_to_dict(template_obj),
            )
            click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            click.echo(f"✓ テンプレート作成成功: {template_obj.name} (ID: {template_obj.id})")

    except Exception as exc:
        error = format_exception(exc)
        if as_json:
            response = format_response(success=False, error=error)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2), err=True)
        else:
            click.echo(f"✗ エラー: {error['message']}", err=True)
        sys.exit(1)


@template.command('list')
@click.option(
    '--status',
    type=click.Choice(['draft', 'published', 'archived']),
    default=None,
    help='ステータスフィルタ',
)
@click.option('--limit', type=int, default=50, help='取得件数')
@click.option('--offset', type=int, default=0, help='オフセット')
@click.option('--json', 'as_json', is_flag=True, help='JSON形式で出力')
def list_templates(status: str | None, limit: int, offset: int, as_json: bool):
    """テンプレート一覧を表示"""
    try:
        factory = ServiceFactory.get_instance()
        svc = factory.get_template_service()
        templates = svc.list_templates(status=status, limit=limit, offset=offset)

        if as_json:
            response = format_response(
                success=True,
                data=[dataclass_to_dict(t) for t in templates],
            )
            click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            if not templates:
                click.echo("テンプレートがありません")
                return

            for t in templates:
                status_badge = (
                    '📋' if t.status == 'draft'
                    else '✓' if t.status == 'published'
                    else '⊘'
                )
                click.echo(
                    f"{status_badge} [{t.id}] {t.name} ({t.status})"
                )

    except Exception as exc:
        error = format_exception(exc)
        if as_json:
            response = format_response(success=False, error=error)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2), err=True)
        else:
            click.echo(f"✗ エラー: {error['message']}", err=True)
        sys.exit(1)


@template.command('show')
@click.argument('template_id', type=int)
@click.option('--json', 'as_json', is_flag=True, help='JSON形式で出力')
def show(template_id: int, as_json: bool):
    """テンプレート詳細を表示"""
    try:
        factory = ServiceFactory.get_instance()
        svc = factory.get_template_service()
        template_obj = svc.get_template(template_id)

        if as_json:
            response = format_response(
                success=True,
                data=dataclass_to_dict(template_obj),
            )
            click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            click.echo(f"\n📋 テンプレート: {template_obj.name}")
            click.echo(f"   ID: {template_obj.id}")
            click.echo(f"   Status: {template_obj.status}")
            if template_obj.description:
                click.echo(f"   説明: {template_obj.description}")
            if template_obj.created_by:
                click.echo(f"   作成者: {template_obj.created_by}")

            if template_obj.phases:
                click.echo(f"\n   フェーズ ({len(template_obj.phases)} 個):")
                for phase in template_obj.phases:
                    click.echo(f"     • [{phase.id}] {phase.phase_label} ({phase.specialist_type})")
                    if phase.tasks:
                        for task in phase.tasks:
                            click.echo(f"       - {task.task_key}: {task.task_title}")

    except Exception as exc:
        error = format_exception(exc)
        if as_json:
            response = format_response(success=False, error=error)
            click.echo(json.dumps(response, ensure_ascii=False, indent=2), err=True)
        else:
            click.echo(f"✗ エラー: {error['message']}", err=True)
        sys.exit(1)
