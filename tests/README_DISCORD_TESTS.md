# Discord 連携信頼性テスト実装ガイド

## 概要

このドキュメントは、THEBRANCH の Discord 連携機能の信頼性テスト（タスク #2041）の実装ガイドです。

- **テスト対象**: `scripts/discord_notifier.py`
- **テストフレームワーク**: pytest + pytest-bdd
- **テストシナリオ**: `features/discord-reliability.feature`
- **ステップ定義**: `tests/step_defs/test_discord_reliability.py`

---

## テスト対象の機能

### 1. **メッセージ送信の基本機能**
- テキストメッセージの送信
- JSON 形式でのメッセージボディ構築
- Authorization ヘッダーの設定
- User-Agent ヘッダーの設定

### 2. **認証情報の取得**
- Discord Bot トークンの読み込み（`.env` ファイル）
- チャンネル ID の読み込み（`channel_id` ファイル）
- 環境変数からのフォールバック

### 3. **エラーハンドリング**
- トークン不足時の処理（False 返却）
- チャンネル ID 不足時の処理
- ネットワークエラー時の処理
- API エラー（401, 403）時の処理
- タイムアウト（10秒）の検証

### 4. **信頼性・耐障害性**
- 複数メッセージの順序保証送信
- 部分失敗時の正確な記録
- 同時実行時のレースコンディション検査
- 一時的エラーからの復旧

---

## セットアップ

### 必要なパッケージ

```bash
pip install pytest pytest-bdd pytest-mock
```

### ディレクトリ構造

```
THEBRANCH/
├── features/
│   └── discord-reliability.feature       # テストシナリオ（BDD）
├── tests/
│   ├── step_defs/
│   │   └── test_discord_reliability.py   # ステップ定義（pytest-bdd）
│   └── README_DISCORD_TESTS.md           # このファイル
└── scripts/
    └── discord_notifier.py               # テスト対象モジュール
```

---

## テスト実行方法

### すべてのテストを実行

```bash
cd /Users/delightone/dev/github.com/adachi-koichi/ai-orchestrator
pytest tests/step_defs/test_discord_reliability.py -v
```

### 特定のシナリオのみ実行

```bash
pytest tests/step_defs/test_discord_reliability.py::test_send_text_message -v
```

### テスト結果の詳細表示

```bash
pytest tests/step_defs/test_discord_reliability.py -vv --tb=long
```

### テスト実行中にログ出力を表示

```bash
pytest tests/step_defs/test_discord_reliability.py -v -s
```

---

## テストシナリオ一覧

### ✅ 通常系（Success Path）

| # | シナリオ名 | 説明 | 期待結果 |
|---|---|---|---|
| 1 | テキストメッセージを送信できる | 単純なメッセージを送信 | POST リクエスト送信、True 返却 |
| 2 | サマリーメッセージを送信できる | タスク統計情報を含むメッセージ | メッセージに統計情報含まれる |
| 3 | 複数メッセージを順序保証で送信できる | 3つのメッセージを順番に送信 | すべて成功、順序保証 |

### ❌ エラー系（Error Path）

| # | シナリオ名 | 条件 | 期待結果 |
|---|---|---|---|
| 4 | トークンが見つからない | `.env` ファイルなし | False 返却、エラーログ出力 |
| 5 | チャンネル ID が見つからない | ファイルなし、環境変数なし | False 返却、エラーログ出力 |
| 6 | Discord API がタイムアウト | 10秒以上応答なし | False 返却、10秒以内に完了 |
| 7 | API が 401 Unauthorized | トークン無効 | False 返却、エラーログ出力 |
| 8 | API が 403 Forbidden | チャンネルアクセス不可 | False 返却、エラーログ出力 |
| 9 | ネットワークエラー | 接続不可 | False 返却、例外ログ出力 |

### 🔄 復旧系（Recovery Path）

| # | シナリオ名 | 条件 | 期待結果 |
|---|---|---|---|
| 10 | 一時的なエラーから復旧 | 1回目失敗、2回目成功 | 1回目 False、2回目 True |
| 11 | 複数メッセージ送信中の部分失敗 | メッセージ2のみ失敗 | 1,3 成功、2失敗、記録正確 |

### 📋 検証系（Validation）

| # | シナリオ名 | 対象 | 検証項目 |
|---|---|---|---|
| 12 | メッセージが JSON エスケープされる | 特殊文字含むメッセージ | `"`, `\`, `\n` が正しくエスケープ |
| 13 | User-Agent ヘッダー設定 | HTTP ヘッダー | "DiscordBot (THEBRANCH, 1.0)" |
| 14 | チャンネル ID フォールバック | 環境変数 | DISCORD_CHANNEL_ID が使用される |
| 15 | 異なるチャンネル ID での送信 | 複数チャンネル | 各チャンネルで正常送信 |
| 16 | タイムアウト = 10秒 | urlopen パラメータ | timeout=10 設定確認 |
| 17 | 同時実行時の並行性 | マルチスレッド | 3スレッド全て成功、RC なし |

---

## テスト実装の進捗

### フェーズ 1: 基本的なステップ定義（実装中 🟡）

以下のステップは実装済み：
- ✅ Background: トークン・チャンネル ID 設定
- ✅ Scenario 1: メッセージ送信
- ✅ Scenario 2: トークン不足
- ✅ Scenario 3: タイムアウト
- ✅ Scenario 4: フォールバック

実装待機中：
- ⏳ 401/403 エラー処理
- ⏳ ネットワークエラー処理
- ⏳ メッセージ順序保証の検証
- ⏳ JSON エスケープ検証

### フェーズ 2: 拡張テストケース（設計段階）

以下の追加ケースが必要：
- 部分失敗時の結果記録
- 同時実行性テスト（マルチスレッド）
- パフォーマンステスト（複数メッセージの速度）

### フェーズ 3: E2E テスト（計画段階）

実際の Discord API との連携テスト：
- 実運用トークンでの送信テスト（CI/CD 外で手動実行）
- 本番環境での動作確認

---

## モック戦略

テストは以下の項目をモック化します：

### モック対象

| 対象 | モック方法 | 理由 |
|---|---|---|
| `urllib.request.urlopen` | `patch()` + `Mock` | 実 API 呼び出しを避ける |
| `load_discord_token()` | `patch()` で戻り値設定 | トークン存在確認を制御 |
| `load_channel_id()` | `patch()` で戻り値設定 | チャンネル ID 存在確認を制御 |
| ファイル I/O | `tmp_path` fixture | 実ファイルを避ける |

### 実行対象

| 対象 | 実行方法 | 理由 |
|---|---|---|
| `send_message()` | 実装を実行 | ビジネスロジックの検証 |
| JSON 構築 | 実装を実行 | JSON エスケープの検証 |
| HTTP ヘッダー構築 | 実装を実行 | ヘッダー正確性の確認 |

---

## テスト結果の解釈

### 成功（✅）

```
tests/step_defs/test_discord_reliability.py::test_send_text_message PASSED
```

- すべてのステップが実行された
- モックが期待通り動作した
- アサーションがすべて通った

### 失敗（❌）

```
tests/step_defs/test_discord_reliability.py::test_timeout_handling FAILED
AssertionError: assert True != False
```

- ステップ定義のアサーションが失敗
- 実装コードに問題がある可能性
- モック設定の確認が必要

### スキップ（⊘）

```
tests/step_defs/test_discord_reliability.py::test_network_error_handling SKIPPED
```

- 依存関係が満たされていない
- 必要なモックが未設定

---

## トラブルシューティング

### モジュールインポートエラー

```
ModuleNotFoundError: No module named 'discord_notifier'
```

**解決策**: `sys.path.insert(0, ...)` でスクリプトディレクトリをパスに追加

```python
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
```

### モック戻り値が効かない

```python
# ❌ 間違い
@patch("discord_notifier.send_message")
def test_something(mock_send):
    # mock_send を設定したが、実装内で import したパスが違う場合失敗

# ✅ 正しい
with patch("urllib.request.urlopen") as mock_urlopen:
    # 実装内で使われている具体的なパスをモック
```

### ファイル I/O がテンポラリディレクトリで失敗

```python
# ✅ 正しい: HOME を一時的に変更
@pytest.fixture
def mock_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path
```

---

## パフォーマンス測定

### テスト実行時間

```bash
pytest tests/step_defs/test_discord_reliability.py -v --durations=10
```

### 期待される実行時間

- **単一メッセージ送信**: 0.1 秒以下
- **複数メッセージ（3個）**: 0.3 秒以下
- **タイムアウト テスト**: 最大 15 秒（タイムアウト 10 秒 + オーバーヘッド）
- **全テストスイート**: 30 秒以下

---

## CI/CD 統合

### GitHub Actions 例

```yaml
name: Discord Reliability Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: pip install pytest pytest-bdd pytest-mock
      - name: Run tests
        run: cd /path/to/ai-orchestrator && pytest tests/step_defs/test_discord_reliability.py -v
```

---

## 次のステップ

### ✅ 完了項目

- [x] BDD シナリオ（`.feature`）の作成
- [x] ステップ定義の基礎実装
- [x] テスト実行ガイドの作成

### ⏳ 実装中

- [ ] 残りのステップ定義実装
- [ ] 401/403 エラーテスト完成
- [ ] JSON エスケープテスト完成
- [ ] ローカルテスト実行・検証

### 🔄 次フェーズ

- [ ] 部分失敗シナリオの実装
- [ ] マルチスレッド同時実行テスト
- [ ] パフォーマンステスト
- [ ] E2E テスト（実 API との連携）

---

## 参考資料

- [pytest ドキュメント](https://docs.pytest.org/)
- [pytest-bdd チュートリアル](https://pytest-bdd.readthedocs.io/)
- [discord.py ドキュメント](https://discordpy.readthedocs.io/)
- [Discord API リファレンス](https://discord.com/developers/docs/reference)

---

## お問い合わせ

テスト実装に関する質問は、タスク #2041 コメントセクションに記入してください。
