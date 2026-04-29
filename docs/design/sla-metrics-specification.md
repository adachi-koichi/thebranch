# SLA Metrics Calculation Specification

## 概要

SLAメトリクスは、AIエージェントのサービス品質を定量的に測定するための3つの指標を定義する。

---

## 3つのメトリクス

### 1. 応答時間（Response Time）

#### 定義

HTTPリクエストの送信からレスポンス受信完了までの経過時間（ミリ秒）。

#### 計算式

```
Response Time (ms) = response_end_time - request_start_time
```

#### 計算例

```
request_start_time    = 100ms (from request initiation)
response_end_time     = 550ms (when last byte of response received)
response_time         = 550 - 100 = 450ms
```

#### SLA違反判定

```
violation = response_time > response_time_limit_ms

例: response_time_limit_ms = 500
    450ms は OK
    510ms は VIOLATION
```

#### 実装仕様

- **測定方式**: HTTPクライアント・ライブラリの自動計測
- **サンプリング**: すべてのHTTPリクエストを計測
- **精度**: ミリ秒単位（小数点以下は切り上げ）
- **集約**: 1分ごとに平均値・最大値・最小値を計算

#### 例：1分間のサンプル
```
Sample 1: 450ms
Sample 2: 480ms
Sample 3: 490ms
Sample 4: 510ms (VIOLATION)
Sample 5: 440ms

統計値：
平均値: (450+480+490+510+440) / 5 = 474ms
最大値: 510ms
最小値: 440ms
違反数: 1件（510ms）
```

---

### 2. 稼働率（Uptime Percentage）

#### 定義

AIエージェントが正常に稼働している時間の割合。

#### 計算式

```
Uptime % = (operating_time / total_time) × 100

where:
  operating_time = 正常に稼働していた時間（秒）
  total_time     = 監視対象の総時間（秒）
```

#### 計算例

```
total_time     = 3600秒（1時間）
downtime       = 30秒（接続失敗・502 Bad Gateway等）
operating_time = 3600 - 30 = 3570秒
uptime %       = (3570 / 3600) × 100 = 99.17%
```

#### SLA違反判定

```
violation = uptime % < target_uptime %

例: target_uptime % = 99.5%
    99.5% 以上    = OK
    99.4%以下     = VIOLATION
```

#### ダウンタイムの分類

| 分類 | 判定基準 | 例 |
|------|---------|-----|
| オンライン | HTTP 200-399 | 正常に応答 |
| クライアント側エラー | HTTP 400-499 | 不正なリクエスト（SLA計算に含めない） |
| サーバー側エラー | HTTP 500-599 | サーバーダウン、タイムアウト（ダウンタイムとして計算） |
| ネットワークエラー | No response | 接続失敗（ダウンタイムとして計算） |

#### 実装仕様

- **計測期間**: ローリングウィンドウ（直近60分、24時間単位で週単位統計）
- **計測方式**: 周期的なヘルスチェック（30秒ごと）
- **精度**: 小数点以下2桁まで
- **集約**: 1時間ごとの稼働率を計算

#### 例：24時間の稼働率
```
時刻        稼働秒数  総秒数  稼働率
00:00-01:00 3600     3600    100.00%
01:00-02:00 3570     3600    99.17%
02:00-03:00 3600     3600    100.00%
...
23:00-24:00 3600     3600    100.00%

24時間稼働率 = (全稼働秒数 / 全秒数) × 100 = 99.98%
```

---

### 3. エラー率（Error Rate）

#### 定義

APIリクエストのうち、HTTP 4xx/5xx エラーで返されたリクエストの割合。

#### 計算式

```
Error Rate (%) = (error_count / total_request_count) × 100

where:
  error_count      = HTTP 4xx/5xx のレスポンスコード数
  total_request_count = 合計リクエスト数
```

#### 計算例

```
total_request_count = 1000リクエスト
error_4xx_count     = 3件（400 Bad Request等）
error_5xx_count     = 5件（500 Internal Server Error等）
error_count         = 3 + 5 = 8件

error_rate (%)  = (8 / 1000) × 100 = 0.8%
```

#### SLA違反判定

```
violation = error_rate > error_rate_limit

例: error_rate_limit = 0.1%（0.001）
    0.08% は OK
    0.12% は VIOLATION
```

#### エラー分類

| HTTPコード | 分類 | SLA計上 |
|-----------|------|--------|
| 200-299 | 成功 | × |
| 300-399 | リダイレクト | × |
| 400-499 | クライアントエラー | ○（エラー計上） |
| 500-599 | サーバーエラー | ○（エラー計上） |

#### 実装仕様

- **計測方式**: APIゲートウェイのアクセスログ解析
- **サンプリング**: すべてのHTTPレスポンスコードを計測
- **精度**: 小数点以下2桁まで
- **集約**: 5分ごと・1時間ごと・24時間ごとに計算

#### 例：1時間のエラー集計
```
時刻        総リクエスト数  エラー数  エラー率
00:00-00:05 200             0        0.00%
00:05-00:10 210             2        0.95%
00:10-00:15 205             0        0.00%
00:15-00:20 195             1        0.51%
00:20-00:25 200             0        0.00%
00:25-00:30 190             0        0.00%
...

1時間合計   10000           42       0.42%
```

---

## メトリクス集約ルール

### 計測周期と集約

| 周期 | 計測方式 | 保存期間 |
|------|---------|---------|
| 1分 | リアルタイム計測 | 24時間 |
| 5分 | 細粒度集約 | 7日間 |
| 1時間 | 標準集約 | 30日間 |
| 24時間 | 日次集約 | 1年間 |

### 集約方法

```python
# 応答時間の集約
response_time_1h = {
    'avg': mean(response_times_1h),
    'max': max(response_times_1h),
    'min': min(response_times_1h),
    'p95': percentile(response_times_1h, 95),
    'p99': percentile(response_times_1h, 99)
}

# 稼働率の集約
uptime_1h = sum(operating_seconds) / sum(total_seconds) * 100

# エラー率の集約
error_rate_1h = sum(error_count) / sum(total_request_count) * 100
```

---

## SLA違反検出ルール

### 違反の種類

| 違反タイプ | 判定条件 | 重要度 |
|----------|---------|-------|
| RESPONSE_TIME_EXCEEDED | response_time > limit | HIGH |
| UPTIME_BELOW_TARGET | uptime < target | CRITICAL |
| ERROR_RATE_EXCEEDED | error_rate > limit | HIGH |

### 重要度レベル

| 重要度 | 対応時間 | アクション |
|-------|---------|----------|
| CRITICAL | 即座（5分以内） | 即時アラート + エスカレーション |
| HIGH | 15分以内 | アラート + 担当者通知 |
| MEDIUM | 1時間以内 | ログ記録 + ダッシュボード表示 |
| LOW | 翌営業日 | ログ記録 |

### 検出サイクル

- **リアルタイム検出**: 各メトリクス計測直後（1分以内）
- **バッチ検出**: 5分ごとの集約後
- **アラート送信**: 同一違反は24時間ごとに送信（重複抑止）

---

## データ保存と監査

### sla_metrics テーブル設計

```sql
sla_metrics:
  - id: INTEGER PRIMARY KEY
  - policy_id: INTEGER FOREIGN KEY
  - response_time_ms: INTEGER
  - uptime_percentage: REAL
  - error_rate: REAL
  - measured_at: TIMESTAMP
```

### sla_violations テーブル設計

```sql
sla_violations:
  - id: INTEGER PRIMARY KEY
  - policy_id: INTEGER FOREIGN KEY
  - metric_id: INTEGER FOREIGN KEY
  - violation_type: TEXT (RESPONSE_TIME_EXCEEDED | UPTIME_BELOW_TARGET | ERROR_RATE_EXCEEDED)
  - severity: TEXT (CRITICAL | HIGH | MEDIUM | LOW)
  - details: TEXT
  - alert_sent: BOOLEAN
  - resolved_at: TIMESTAMP (NULL until resolved)
  - created_at: TIMESTAMP
```

---

## 計測例：総合シナリオ

### ステップ1: リクエスト送受信

```
Request A: 時刻 0:00:10, 応答時間 450ms → 正常
Request B: 時刻 0:00:15, 応答時間 520ms → 違反（limit=500ms）
Request C: 時刻 0:00:20, 応答時間 480ms → 正常
...
```

### ステップ2: 1分集約

```
1分間（0:00:00-0:00:59）の統計：
- 総リクエスト: 100
- エラーレスポンス: 2
- 応答時間平均: 475ms
- ダウンタイム: 0秒

計算結果：
- response_time_ms: 475
- uptime_percentage: 100.0
- error_rate: 2.0
```

### ステップ3: SLA違反検出

```
Policy: Standard
  - response_time_limit_ms: 500 → OK (475 < 500)
  - uptime_percentage: 99.5 → OK (100.0 > 99.5)
  - error_rate_limit: 0.1 → VIOLATION (2.0 > 0.1)

Result: 
  違反タイプ: ERROR_RATE_EXCEEDED
  重要度: HIGH
  アラート送信: YES
```

---

## 参考：計算コード例（Python）

```python
from datetime import datetime

class SLACalculator:
    @staticmethod
    def calculate_response_time(start_ms: int, end_ms: int) -> int:
        """応答時間計算"""
        return max(0, end_ms - start_ms)
    
    @staticmethod
    def calculate_uptime(operating_seconds: int, total_seconds: int) -> float:
        """稼働率計算"""
        if total_seconds == 0:
            return 100.0
        return (operating_seconds / total_seconds) * 100.0
    
    @staticmethod
    def calculate_error_rate(error_count: int, total_count: int) -> float:
        """エラー率計算"""
        if total_count == 0:
            return 0.0
        return (error_count / total_count) * 100.0
    
    @staticmethod
    def check_violation(
        response_time_ms: int,
        response_time_limit: int,
        uptime_pct: float,
        uptime_target: float,
        error_rate: float,
        error_limit: float
    ) -> list:
        """SLA違反判定"""
        violations = []
        
        if response_time_ms > response_time_limit:
            violations.append({
                'type': 'RESPONSE_TIME_EXCEEDED',
                'severity': 'HIGH'
            })
        
        if uptime_pct < uptime_target:
            violations.append({
                'type': 'UPTIME_BELOW_TARGET',
                'severity': 'CRITICAL'
            })
        
        if error_rate > error_limit:
            violations.append({
                'type': 'ERROR_RATE_EXCEEDED',
                'severity': 'HIGH'
            })
        
        return violations
```
