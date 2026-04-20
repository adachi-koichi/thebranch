# Go/No-Go Criteria for Workflow Template System

## 1. 本番判定の意思決定ツリー

```
E2E テスト実行開始
│
├─ 全テストシナリオ実行
│  ├─ テスト PASS 率: 95% 以上？ ──No→ NO-GO（失敗テスト原因調査→改修）
│  └─ YES ↓
│
├─ パフォーマンス検証
│  ├─ 平均応答時間: ≤ 2秒？ ──No→ NO-GO（ボトルネック分析→最適化）
│  └─ YES ↓
│
├─ エラー率検証
│  ├─ エラー率: ≤ 1%？ ──No→ NO-GO（エラー原因分析→修正）
│  └─ YES ↓
│
├─ リスク評価
│  ├─ Critical リスク存在？ ──Yes→ NO-GO（リスク軽減→再評価）
│  └─ NO ↓
│
├─ 承認プロセス
│  ├─ QA 責任者: サインオフ
│  ├─ Engineering Manager: 承認
│  └─ Product Owner: 最終承認
│
└─ **GO** → 本番デプロイ
```

## 2. Go/No-Go 判定基準

### 2.1 テスト実行基準

| 項目 | 基準 | 判定 | 説明 |
|---|---|---|---|
| **全テスト PASS 率** | ≥ 95% | GO | 6個中最大1個の失敗まで許容 |
| | < 95% | NO-GO | 2個以上の失敗は本番不可 |
| **テスト実行カバレッジ** | 100% | GO | 全テストシナリオが実行されていること |
| | < 100% | NO-GO | スキップまたは未実行テストがある場合 |

### 2.2 パフォーマンス基準

| メトリクス | 基準値 | 判定 | 許容値 |
|---|---|---|---|
| **平均応答時間** | ≤ 2.0秒 | GO | Template 作成～Task 生成のエンドツーエンド |
| | 2.0～3.0秒 | CAUTION | 本番環境で要監視 |
| | > 3.0秒 | NO-GO | 最適化必須 |
| **P95 応答時間** | ≤ 4.0秒 | GO | ピーク負荷での95パーセンタイル値 |
| | > 4.0秒 | NO-GO | スケーラビリティ問題の可能性 |
| **データベース接続時間** | ≤ 100ms | GO | SQLite 準備・オープン時間 |

### 2.3 エラー率基準

| メトリクス | 基準値 | 判定 | 対象範囲 |
|---|---|---|---|
| **全体エラー率** | ≤ 1.0% | GO | 本番環境での許容上限 |
| | 1.0～3.0% | CAUTION | 原因調査・改修予定あり |
| | > 3.0% | NO-GO | 本番デプロイ不可 |
| **バリデーションエラー率** | ≤ 0.5% | GO | スペシャリスト検証時 |
| **Database エラー率** | ≤ 0.1% | GO | データベース操作での障害 |

### 2.4 テストシナリオ別合格基準

| シナリオ | 説明 | 合格条件 |
|---|---|---|
| **Create workflow template** | Template + Phase + Task 定義作成 | PASS ＆ 応答時間 ≤ 1秒 |
| **Instantiate template** | Template をインスタンス化して Specialist 割り当て | PASS ＆ 応答時間 ≤ 2秒 |
| **Auto-generate tasks** | Phase ベースのタスク自動生成 | PASS ＆ 全タスク生成 |
| **Reuse template** | 既存 Template の再利用・Specialist 変更 | PASS ＆ データ保全性確認 |
| **Specialist validation error** | 不可能な Specialist で Error 発生 | 予期した Error 発生 ＆ メッセージ正確 |
| **Multiple specialists** | 同一 Phase に複数 Specialist 割り当て | PASS ＆ 並列処理確認 |

## 3. リスク評価表

### 3.1 特定されたリスク一覧

| ID | リスク項目 | 重要度 | 発生確率 | 影響度 | リスク値 | 軽減策 |
|---|---|---|---|---|---|---|
| **R-001** | Template 定義の不整合（Phase 順序逆転） | High | Medium | High | **High** | Phase 順序検証ロジック追加・テスト強化 |
| **R-002** | Specialist 割り当て失敗時の Fallback なし | High | Low | High | **Medium** | Error handling 強化・リトライロジック実装 |
| **R-003** | 大量 Task 生成時のパフォーマンス低下 | Medium | Low | High | **Medium** | バッチ処理最適化・インデックス追加 |
| **R-004** | Database 接続リーク（マルチテナント環境） | Medium | Medium | High | **Medium** | コネクションプール導入・リソース監視 |
| **R-005** | 並列 Specialist 処理時のデッドロック | Medium | Low | Medium | **Low** | トランザクション分離レベル確認・テスト |
| **R-006** | API 応答時間が閾値超過 | Medium | Medium | Medium | **Medium** | Query 最適化・キャッシング導入 |

### 3.2 リスク軽減状況

| リスク ID | 軽減完了 | 残存リスク | 本番許容判定 |
|---|---|---|---|
| R-001 | ✅ Phase 順序テスト追加 | None | ✅ GO |
| R-002 | ✅ Error handling 実装 | Minor | ✅ GO |
| R-003 | ⚠️  バッチ処理 WIP | バッチサイズ検証必須 | CAUTION |
| R-004 | ⚠️  リソース監視機能 WIP | 監視ダッシュボード欠落 | CAUTION |
| R-005 | ✅ テスト実行確認 | None | ✅ GO |
| R-006 | ✅ Query 最適化完了 | None | ✅ GO |

**本番判定: R-003, R-004 の完了を条件に GO 判定**

## 4. テスト実行チェックリスト

### 4.1 事前準備チェック

- [ ] テスト環境セットアップ完了（DB 初期化、FixtureData 投入）
- [ ] 依存パッケージインストール完了（pytest-bdd, pytest）
- [ ] テストデータの妥当性確認（Specialist リスト、Template スキーマ等）
- [ ] モニタリング・ロギング有効化（応答時間計測、エラーログ記録）

### 4.2 テスト実行チェック

```bash
# E2E テスト実行コマンド
pytest tests/workflow/e2e/test_scenarios.py -v --tb=short --html=report.html

# メトリクス計測
pytest tests/workflow/e2e/test_scenarios.py --durations=10
```

- [ ] 全テスト実行完了
- [ ] テスト PASS 率 ≥ 95% 確認
- [ ] 平均応答時間 ≤ 2.0秒 確認
- [ ] エラー率 ≤ 1.0% 確認
- [ ] テストレポート生成（HTML）
- [ ] パフォーマンスプロファイル取得

### 4.3 結果分析チェック

- [ ] 失敗テストの原因分析（失敗メッセージ確認）
- [ ] エラーログ確認（DB エラー、例外スタックトレース）
- [ ] パフォーマンスログ確認（遅いクエリ、ボトルネック特定）
- [ ] リスク評価の再確認（新規リスク検出）
- [ ] 本番環境でのシナリオ予測

## 5. 承認者・確認者リスト

### 5.1 承認・サインオフ権限

| 役割 | 名前 | 責務 | サインオフ権限 |
|---|---|---|---|
| **QA 責任者** | QA Lead | テスト実行結果・メトリクス検証 | ✅ Functional GO/NO-GO |
| **Engineering Manager** | EM | コード品質・リスク評価確認 | ✅ Technical GO/NO-GO |
| **Product Owner** | PO | ビジネス要件の充足確認 | ✅ Final GO/NO-GO |

### 5.2 確認者（レビュー・検証）

| 役割 | 名前 | 確認内容 |
|---|---|---|
| **Senior Engineer** | Tech Lead | パフォーマンス・セキュリティ検証 |
| **Database Specialist** | DB Engineer | Query 最適化・インデックス確認 |
| **DevOps Lead** | DevOps | 本番環境への影響度評価 |

### 5.3 サインオフ書式

```markdown
## Go/No-Go Decision Form

**Date**: YYYY-MM-DD  
**Decision**: GO / NO-GO  

### QA 確認
- Test PASS Rate: ___%
- Average Response Time: ___ms
- Error Rate: ___%
- Signature: _______________ Date: __________

### Engineering Lead
- Code Quality: ✅ / ⚠️  / ❌
- Risk Assessment: ✅ / ⚠️  / ❌
- Signature: _______________ Date: __________

### Product Owner
- Business Requirement: ✅ / ⚠️  / ❌
- Signature: _______________ Date: __________

### Comments
_________________________________________
```

## 6. 本番デプロイ判定フロー

### 6.1 GO 判定時の手順

1. 全承認者によるサインオフ取得
2. 本番環境への準備確認（リソース、バックアップ等）
3. デプロイスケジュール確認
4. ロールバックプラン確認
5. デプロイ実行（段階的ロールアウト推奨）

### 6.2 NO-GO 判定時の対応

1. 失敗原因の詳細分析レポート作成
2. 改修プラン・スケジュール作成
3. リスク再評価
4. 再テスト実行スケジュール決定
5. ステークホルダーへの報告

## 7. 付録：パフォーマンス測定方法

### 7.1 応答時間計測

```python
import time
from functools import wraps

def measure_response_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = (time.time() - start) * 1000  # ms
        print(f"[PERF] {func.__name__}: {duration:.2f}ms")
        return result
    return wrapper
```

### 7.2 エラー率計測

```python
# エラー率 = (失敗テスト数 / 全テスト数) × 100
error_rate = (failed_count / total_count) * 100
```

### 7.3 レポート生成

```bash
pytest tests/workflow/e2e/test_scenarios.py \
  --html=report.html \
  --self-contained-html \
  --durations=10 \
  -v
```

---

**ドキュメント版: v1.0**  
**最終更新: 2026-04-18**  
**本番判定責任者: QA Lead / Engineering Manager / Product Owner**
