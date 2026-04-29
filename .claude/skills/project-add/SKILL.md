---
name: project-add
description: THEBRANCHにプロジェクトを追加・管理するスキル。「プロジェクトを追加」「プロジェクト作成」「/project-add」と言われたとき、またはプロジェクト・ワークフロー・タスクの構造をDBに登録したいときに使う。
---

# project-add スキル

thebranch.sqlite にプロジェクトを追加・管理する。  
コアロジックは `workflow/services/project_service.py` に実装済み。  
このスキルはその CLI ラッパー / 使い方ガイドとして機能する。

## アーキテクチャ

```
Project（プロジェクト）
  └── Workflow × N   sequential / parallel
        └── Task × N   AIエージェントがアサインされて実行
```

## CLI 使用例

```bash
cd ~/dev/github.com/adachi-koichi/thebranch

# プロジェクトを追加（JSON ファイル）
python3 .claude/skills/project-add/scripts/project_add.py add --json-file project.json

# プロジェクトを追加（JSON 文字列）
python3 .claude/skills/project-add/scripts/project_add.py add --json-str '{"name":"テスト","workflows":[]}'

# プロジェクト一覧
python3 .claude/skills/project-add/scripts/project_add.py list

# プロジェクト詳細（ワークフロー・タスク含む）
python3 .claude/skills/project-add/scripts/project_add.py show --id 1

# プロジェクト削除
python3 .claude/skills/project-add/scripts/project_add.py delete --id 1
```

## API エンドポイント（UIからも利用可）

| Method | Path | 説明 |
|---|---|---|
| GET | `/api/projects` | 一覧（?status=active 等でフィルタ可） |
| POST | `/api/projects` | 新規作成（ProjectSpec JSON を body に） |
| GET | `/api/projects/{id}` | 詳細（ワークフロー・フェーズ・タスク含む） |
| PATCH | `/api/projects/{id}` | 更新（name/description/status） |
| DELETE | `/api/projects/{id}` | 削除 |

## spec フォーマット

```json
{
  "name": "プロジェクト名",
  "description": "説明",
  "status": "active",
  "workflows": [
    {
      "name": "ワークフロー名",
      "description": "説明",
      "execution_mode": "sequential",
      "tasks": [
        {
          "key": "task-001",
          "title": "タスクタイトル",
          "description": "詳細",
          "specialist_type": "engineer",
          "execution": "sequential",
          "depends_on": "task-000",
          "priority": 1,
          "estimated_hours": 2.0
        }
      ]
    }
  ]
}
```

### フィールド説明

| フィールド | 値 | 説明 |
|---|---|---|
| `execution_mode` | `sequential` / `parallel` | 前のワークフローとの実行関係 |
| `specialist_type` | `engineer` / `designer` / `researcher` / `product_manager` | タスク担当エージェント種別 |
| `execution` | `sequential` / `parallel` | フェーズ内の並行実行有無 |
| `priority` | `1` / `2` / `3` | 1=高 2=中 3=低 |

## 手順（このスキルを使うとき）

1. ユーザーが何を作りたいかヒアリング（プロジェクト名・ワークフロー・タスク構成）
2. spec JSON を組み立てる
3. `project_add.py add --json-str '...'` または API POST `/api/projects` で登録
4. 登録結果（project_id）を返す
