# THEBRANCH

## アプリケーション概要

**THEBRANCH** - AIエージェント部署を作成・運営できるプラットフォーム。

> 組織は、生まれながらの特権ではない。
> アイデアを持つすべての個人が、翌朝から機能する組織を手にできる世界。
> 採用でも外注でもなく、部署ごと、AIで動かす。
> ひとりが、ユニコーンになれる時代へ。

---

## ディレクトリ構成

```
thebranch/
├── dashboard/          # Web UI（Flask/Python）
│   ├── app.py         # メインアプリ
│   ├── auth.py        # 認証
│   ├── models.py      # データモデル
│   ├── migrations/    # DBマイグレーション
│   └── requirements.txt
├── workflow/           # バックエンド業務フローエンジン（Python）
│   ├── services/      # ビジネスロジック
│   ├── repositories/  # データアクセス
│   ├── models/        # ドメインモデル
│   └── validation/    # バリデーション
├── features/           # BDDテスト（Gherkin）
├── design/             # 設計ドキュメント
├── docs/               # プロダクトドキュメント
│   ├── design/        # UX・デザインシステム
│   ├── product/       # プロトタイプ・仕様
│   ├── feature_spec.md
│   ├── personas.md
│   └── validation_report.md
├── slides/             # ピッチデッキ・プレゼン
├── ideas/              # アイデアメモ
├── tests/              # テストスイート
└── test_uat/           # UATテスト
```

## 技術スタック

- **フロントエンド**: HTML/CSS/JS（dashboard/index.html）
- **バックエンド**: Python/Flask（dashboard/app.py）
- **データ**: SQLite（タスク管理）+ KuzuDB（グラフ関係）
- **テスト**: pytest + Gherkin BDD

## 開発ルール

- 設計→実装→テスト→E2Eテストの順で実行
- 実装後は必ず動作確認すること
- 全データにIDを振り、ID管理で情報の関連性を把握し続けること
- SQLiteとKuzuDBで管理し、意図しない中断でも復旧できる構造にすること

## オーケストレーター連携

- タスク管理: `~/.claude/skills/task-manager-sqlite/scripts/task.py`
- 監視・実行: `~/dev/github.com/adachi-koichi/ai-orchestrator/` (オーケストレーターシステム)
- THEBRANCHのプロダクトビジョンに従いタスクを委譲・実行する
