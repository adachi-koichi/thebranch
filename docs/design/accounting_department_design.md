# 経理部AIエージェント基盤設計

## 概要
経理部は以下の3つの主要なワークフローを管理：
1. **請求書処理フロー** - 請求書の作成・承認・支払い管理
2. **経費精算フロー** - 経費申請・承認・実費精算
3. **月次レポート生成** - 会計レポート・決算データ生成

## テーブル構成

### 1. invoices（請求書）
- `id`: INTEGER PRIMARY KEY
- `department_id`: INT, 部署ID
- `invoice_number`: TEXT UNIQUE, 請求書番号
- `vendor_id`: INT, 仕入先ID
- `issue_date`: TEXT, 発行日
- `due_date`: TEXT, 支払期限
- `total_amount_jpy`: REAL, 合計金額
- `tax_amount_jpy`: REAL, 税額
- `status`: TEXT, ステータス (draft/approved/paid/cancelled)
- `approval_status`: TEXT, 承認ステータス (pending/approved/rejected)
- `approved_by`: TEXT, 承認者
- `approved_at`: TEXT, 承認日時
- `paid_date`: TEXT, 支払日
- `payment_method`: TEXT, 支払い方法
- `notes`: TEXT, 備考
- `created_at`, `updated_at`

### 2. invoice_items（請求書行項目）
- `id`: INTEGER PRIMARY KEY
- `invoice_id`: INT, 請求書ID
- `item_description`: TEXT, 項目説明
- `quantity`: REAL, 数量
- `unit_price_jpy`: REAL, 単価
- `amount_jpy`: REAL, 金額
- `created_at`, `updated_at`

### 3. expense_reports（経費申請）
- `id`: INTEGER PRIMARY KEY
- `department_id`: INT, 部署ID
- `employee_id`: INT, 従業員ID
- `report_number`: TEXT UNIQUE, 申請番号
- `report_date`: TEXT, 申請日
- `period_start`: TEXT, 対象期間開始
- `period_end`: TEXT, 対象期間終了
- `total_amount_jpy`: REAL, 合計金額
- `status`: TEXT, ステータス (draft/submitted/approved/rejected/paid)
- `approval_status`: TEXT, 承認ステータス (pending/approved/rejected)
- `approved_by`: TEXT, 承認者
- `approved_at`: TEXT, 承認日時
- `paid_date`: TEXT, 支払日
- `rejection_reason`: TEXT, 却下理由
- `notes`: TEXT, 備考
- `created_at`, `updated_at`

### 4. expense_items（経費項目）
- `id`: INTEGER PRIMARY KEY
- `expense_report_id`: INT, 経費申請ID
- `category`: TEXT, 費目 (transportation/meal/accommodation/office_supplies/other)
- `description`: TEXT, 説明
- `amount_jpy`: REAL, 金額
- `receipt_image_path`: TEXT, レシート画像パス
- `created_at`, `updated_at`

### 5. monthly_accounting_reports（月次レポート）
- `id`: INTEGER PRIMARY KEY
- `department_id`: INT, 部署ID
- `year`: INT, 会計年度
- `month`: INT, 月
- `total_invoiced_jpy`: REAL, 請求合計
- `total_expenses_jpy`: REAL, 経費合計
- `total_approved_jpy`: REAL, 承認合計
- `pending_approval_jpy`: REAL, 待機中
- `report_generated_at`: TEXT, レポート生成日時
- `generated_by`: TEXT, 生成者
- `created_at`, `updated_at`

### 6. accounting_summary（会計概要）
- `id`: INTEGER PRIMARY KEY
- `department_id`: INT, 部署ID
- `year`: INT, 会計年度
- `month`: INT, 月
- `invoice_count`: INT, 請求書数
- `invoice_total_jpy`: REAL, 請求合計
- `expense_count`: INT, 経費申請数
- `expense_total_jpy`: REAL, 経費合計
- `top_category`: TEXT, 最大費目
- `category_breakdown`: TEXT, JSON, 費目別集計
- `created_at`, `updated_at`

## API Endpoints

### 請求書管理
- `POST /api/accounting/invoices` - 請求書作成
- `GET /api/accounting/invoices/{id}` - 請求書取得
- `GET /api/accounting/invoices` - 請求書一覧
- `PUT /api/accounting/invoices/{id}` - 請求書更新
- `POST /api/accounting/invoices/{id}/approve` - 請求書承認
- `POST /api/accounting/invoices/{id}/pay` - 支払い処理
- `DELETE /api/accounting/invoices/{id}` - 請求書削除

### 経費精算
- `POST /api/accounting/expenses` - 経費申請作成
- `GET /api/accounting/expenses/{id}` - 経費申請取得
- `GET /api/accounting/expenses` - 経費申請一覧
- `PUT /api/accounting/expenses/{id}` - 経費申請更新
- `POST /api/accounting/expenses/{id}/approve` - 承認
- `POST /api/accounting/expenses/{id}/reject` - 却下
- `POST /api/accounting/expenses/{id}/pay` - 精算
- `DELETE /api/accounting/expenses/{id}` - 削除

### レポート
- `GET /api/accounting/reports/monthly/{year}/{month}` - 月次レポート
- `GET /api/accounting/reports/department/{dept_id}/{year}` - 部署年間レポート
- `GET /api/accounting/reports/summary` - サマリーレポート
- `GET /api/accounting/reports/category-breakdown` - 費目別集計

## ワークフロー設計

### 請求書処理フロー
```
draft → submitted → approved → paid → closed
         ↓
      rejected
```

### 経費精算フロー
```
draft → submitted → approved → paid → closed
                  ↓
                rejected
```

## サービス層責務

### AccountingService
- 請求書CRUD・承認フロー管理
- 経費申請CRUD・承認フロー管理
- 月次集計処理
- レポート生成
- 承認ワークフロー管理

### AccountingRepository
- 請求書テーブルアクセス
- 経費申請テーブルアクセス
- レポートテーブルアクセス
- インデックス最適化クエリ

## 実装優先度
1. DBマイグレーション（テーブル・インデックス作成）
2. AccountingRepository実装
3. AccountingService実装
4. APIエンドポイント実装
5. 動作確認・テスト
