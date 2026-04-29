# Wave25 カスタマーサポート部AIエージェント基盤 実装戦略

**バージョン**: 1.0  
**作成日**: 2026-04-30  
**ステータス**: 設計フェーズ  
**対象**: Wave25プロダクト対応カスタマーサポート部AIエージェント

---

## 1. 概要

### 1.1 目的

Wave25カスタマーサポート部AIエージェント基盤は、カスタマーサポートチームの自動化・効率化を目指すエージェントシステムです。顧客からの質問や問題報告を自動分類・応答し、エスカレーション判定によって人間の介入が必要な場合を適切に振り分けます。

**主要な役割**:
- カスタマーサポート質問の自動分類（バグ修正・仕様確認・エスカレーション判定）
- 自動応答の生成・配信
- ユーザーへのエスカレーション判定・通知
- サポートナレッジベースとの統合

### 1.2 既存実装との関係性

THEBRANCHプラットフォームの構成要素：

```
THEBRANCH
├─ 既存部署エージェント
│  ├─ exp-stock（株式分析）
│  ├─ breast-cancer（医療分析）
│  └─ line-stamp（ブランド運営）
└─ Wave25 カスタマーサポート部 ← 本実装対象
   ├─ question_classifier（質問分類）
   ├─ auto_responder（自動応答）
   ├─ escalation_handler（エスカレーション制御）
   └─ knowledge_integration（ナレッジベース統合）
```

### 1.3 他の部署エージェントとの違い

| 項目 | exp-stock | breast-cancer | line-stamp | カスタマーサポート |
|------|-----------|----------------|-----------|-----------------|
| **主業務** | 株式分析・推奨 | 医療データ解析 | ブランド運営 | 顧客サポート対応 |
| **入力形式** | 銘柄コード・市場データ | 臨床データ | マーケティングKPI | 自由形式の質問文 |
| **処理パターン** | 計算→分析→推奨 | データ解析→レポート生成 | イベント管理→コンテンツ配信 | 分類→応答→エスカレーション |
| **応答形式** | 構造化分析レポート | 統計・グラフレポート | イベントスケジュール | 自然言語応答 |
| **エスカレーション** | なし | なし | マネージャー判定 | 多段階エスカレーション |
| **ナレッジ連携** | マーケットデータAPI | 医学文献DB | コンテンツDB | FAQナレッジベース |

**カスタマーサポートの特性**:
- 入力の自由度が高い（自然言語による多様な質問形式）
- 分類ロジックが複雑（同一質問でも文脈により異なる処理が必要）
- 人間との協調が重要（自動応答では対応できないケースの割合が高い）
- リアルタイム対応が要求される（顧客満足度への影響が直接的）

---

## 2. アーキテクチャ設計

### 2.1 全体システムアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                   カスタマーサポート UI                      │
│              （Dashboard / チャットインターフェース）          │
└──────────┬──────────────────────────────────────────────────┘
           │ カスタマー質問
           ↓
┌─────────────────────────────────────────────────────────────┐
│                 Question Classifier                          │
│  入力: 自由形式の質問文                                       │
│  処理: キーワード分析 + NLU意図認識 + コンテキスト判定       │
│  出力: 分類カテゴリ                                          │
└──────────┬──────────────────────────────────────────────────┘
           │
      ┌────┴────────────────────────────────────────┐
      ↓                                              ↓
   [自動処理]                               [人間判定]
      │                                              │
   ┌──┴──────────────────────────────────────┐  ┌──┴────────────────────┐
   │                                          │  │                       │
   ↓                                          ↓  ↓                       ↓
┌──────────────────────┐  ┌─────────────────────────────┐  ┌─────────────────┐
│ Auto Responder       │  │  Escalation Handler         │  │  Knowledge Base │
│                      │  │  - エスカレーション判定      │  │  - FAQナレッジ  │
│ - 応答テンプレート   │  │  - ユーザー通知             │  │  - ドキュメント │
│ - 変数埋め込み       │  │  - 優先度設定               │  │  - ベストプラ   │
│ - 応答生成           │  │  - チーム割当               │  │                 │
└──────┬───────────────┘  └─────────────┬───────────────┘  └────────┬────────┘
       │                                 │                           │
       │                                 │                           │
       └────┬────────────────────────────┴───────────────────────────┘
            │
            ↓
   ┌─────────────────────────┐
   │   Response Pipeline     │
   │ - フォーマット          │
   │ - 外部API連携          │
   │ - 監査ログ記録          │
   └─────────────┬───────────┘
                 │
                 ↓
        ┌─────────────────┐
        │  Response DB    │
        │ - 履歴管理      │
        │ - メトリクス    │
        │ - フィードバック│
        └─────────────────┘
```

### 2.2 Question Classifier の実装パターン

**既存実装から**（tests/test_question_classifier.py）:

```python
def classify_question(question: str, context: dict) -> str:
    """
    質問を分類する。
    
    戻り値:
    - "auto_approve": 自動承認可能（バグ修正、supervisor再起動など）
    - "needs_review": レビュー必要（アーキテクチャ決定など）
    - "escalate": エスカレーション必要（プロダクト方向性、チーム設定など）
    - "unknown": 分類不可
    """
```

**Wave25カスタマーサポート向けの拡張分類**:

```python
class QuestionCategory(Enum):
    # Tier 1: 自動応答可能
    AUTO_RESPOND = "auto_respond"              # FAQ回答可能
    AUTO_APPROVE = "auto_approve"              # バグ修正・管理操作
    
    # Tier 2: レビュー必要
    NEEDS_REVIEW = "needs_review"              # アーキテクチャ・設計判定
    CLARIFICATION_NEEDED = "clarification"     # 質問の明確化必要
    
    # Tier 3: エスカレーション
    ESCALATE_PRIORITY = "escalate_priority"    # 高優先度エスカレーション
    ESCALATE_SPECIALTY = "escalate_specialty"  # 専門チームへ振分
    ESCALATE_MANAGEMENT = "escalate_mgmt"      # 経営判定
    
    # その他
    UNKNOWN = "unknown"
```

**分類ロジック設計**:

```
入力: question (自由形式テキスト)
     context (カスタマー情報・状況)

Step 1. キーワードマッチング
├─ バグ報告キーワード → "auto_approve"
├─ 機能説明キーワード → "auto_respond"
├─ 価格・契約キーワード → "escalate_specialty"
└─ その他 → Step 2へ

Step 2. NLU意図認識（Claude API）
├─ 意図: {"intent": "bug_report", "severity": "high", ...}
├─ 感情: {"sentiment": "frustrated", "confidence": 0.85}
└─ エンティティ: {"product": "wave25", "feature": "api", ...}

Step 3. コンテキスト判定
├─ カスタマー企業規模 → 優先度調整
├─ 過去のサポート履歴 → 自動応答可能性判定
├─ 同一問題の報告数 → 既知問題判定
└─ サポート時間帯 → エスカレーション必要性判定

Step 4. 確信度評価
└─ confidence < 0.7 → "clarification_needed"
```

### 2.3 Auto Responder の応答パイプライン

**既存実装から**（tests/test_auto_responder.py）:

```python
def generate_response(question: str, category: str, context: dict, 
                     pane_id: str) -> Optional[str]:
    """
    質問に応じた自動応答を生成する。
    
    戻り値:
    - 応答文字列（auto_approve, needs_review）
    - None（escalate - ユーザーに見せない）
    """

def format_escalation_message(question: str, context: dict, 
                              pane_id: str) -> str:
    """
    ユーザーへのエスカレーションメッセージをフォーマット
    """
```

**カスタマーサポート向けの拡張応答パイプライン**:

```python
class ResponseGenerator:
    """応答生成エンジン"""
    
    def generate_response(self, question: str, category: QuestionCategory,
                         context: SupportContext) -> Response:
        """
        段階的に応答を生成
        """
        # Step 1. テンプレート選択
        template = self.select_template(category, context)
        
        # Step 2. 変数埋め込み（ナレッジベース・FAQから情報取得）
        enriched_response = self.enrich_with_knowledge(
            template, question, context
        )
        
        # Step 3. 応答内容の検証
        validation_result = self.validate_response(enriched_response)
        if not validation_result.is_valid:
            return escalate_response(question, context)
        
        # Step 4. 応答フォーマット
        formatted = self.format_response(enriched_response, context)
        
        # Step 5. 監査ログ記録
        self.log_response_generation(formatted)
        
        return formatted
```

**応答テンプレートの構造**:

```yaml
template_id: "faq_api_rate_limit"
category: "auto_respond"
title: "API レート制限に関するご質問"
priority: "medium"

# テンプレート本体
response: |
  ご質問ありがとうございます。
  
  Wave25 API のレート制限について、以下の通りです：
  
  **レート制限の詳細**:
  - 無料プラン: 100 requests/hour
  - プロプラン: 10,000 requests/hour
  - エンタープライズプラン: 無制限
  
  {{CUSTOMER_PLAN}} プランをご利用中のようですので、
  {{CURRENT_LIMIT}} requests/hour が上限となります。
  
  {{UPGRADE_LINK}}
  
  詳細は {{DOCS_LINK}} をご参照ください。

# 検証ルール
validation:
  min_confidence: 0.8
  requires_context:
    - customer_plan
    - current_usage
  
# 代替応答（検証失敗時）
fallback_template: "escalate_to_support"

# 関連するナレッジベース
related_knowledge:
  - "rate_limit_faq"
  - "upgrade_guide"
  - "api_pricing"
```

### 2.4 エスカレーション処理フロー

```
分類結果: "escalate_*"
    ↓
┌────────────────────────────────────────┐
│  Escalation Handler                    │
├────────────────────────────────────────┤
│                                        │
│  1. エスカレーション優先度決定          │
│     ├─ 顧客企業規模                    │
│     ├─ 質問の重要度                    │
│     └─ 待機中のサポートチケット数      │
│                                        │
│  2. 適切なチームを特定                  │
│     ├─ escalate_specialty:            │
│     │  → 営業チーム / カスタムチーム    │
│     │                                  │
│     ├─ escalate_priority:             │
│     │  → シニアサポートチーム           │
│     │                                  │
│     └─ escalate_management:           │
│        → 管理層 / PM                   │
│                                        │
│  3. チケット生成                        │
│     ├─ チケットID生成                  │
│     ├─ 初期コンテキスト記録             │
│     └─ 優先度・SLA設定                 │
│                                        │
│  4. ユーザー通知                        │
│     ├─ メール配信                      │
│     ├─ UI通知表示                      │
│     └─ エスカレーション理由の説明       │
│                                        │
└────────────────────────────────────────┘
    ↓
マンual Support Team (対応待ち)
```

**エスカレーション判定マトリクス**:

```python
escalation_rules = {
    "high_severity_bug": {
        "conditions": [
            question.contains("crash"),
            question.contains("data loss"),
            question.contains("security"),
        ],
        "target": "escalate_priority",
        "sla_minutes": 30,
    },
    "pricing_negotiation": {
        "conditions": [
            question.contains("discount"),
            question.contains("enterprise"),
            customer.company_size == "enterprise",
        ],
        "target": "escalate_specialty",
        "route_to": "sales_team",
    },
    "product_roadmap": {
        "conditions": [
            question.contains("feature request"),
            question.contains("planned"),
            confidence < 0.6,
        ],
        "target": "escalate_management",
        "route_to": "product_team",
    },
}
```

### 2.5 テンプレート管理システムとの統合

既存の `blueprints.py` / `db_schema.py` から：

**テンプレート階層構造**:

```
workflow_templates (テンプレート定義)
├─ id: 1
├─ name: "Customer Support Escalation Workflow"
├─ category: "support"
├─ status: "active"
├─ config: {...}  ← サポート部固有設定
│
├─ wf_template_phases (フェーズ)
│  ├─ Phase 1: "Question Classification"
│  │  └─ specialist_type: "classifier"
│  ├─ Phase 2: "Auto Response Generation"
│  │  └─ specialist_type: "responder"
│  └─ Phase 3: "Escalation Handling"
│     └─ specialist_type: "escalation_handler"
│
└─ wf_template_tasks (タスク)
   ├─ Task 1.1: "Extract question intent"
   ├─ Task 2.1: "Select response template"
   └─ Task 3.1: "Assign support ticket"
```

**統合ポイント**:

```python
class SupportWorkflowAdapter:
    """
    テンプレートシステムとサポート部オペレーションの連携
    """
    
    def create_support_workflow_instance(
        self,
        question: str,
        customer_id: int,
        category: QuestionCategory
    ) -> WorkflowInstance:
        """
        質問からワークフローインスタンスを生成
        """
        # 1. テンプレート取得
        template = self.template_service.get_template(
            name="Customer Support Escalation Workflow"
        )
        
        # 2. 分類結果に応じてワークフロー構成を調整
        config = self._build_workflow_config(question, category)
        
        # 3. インスタンス生成
        instance = self.template_service.instantiate_template(
            template_id=template.id,
            context={
                "question": question,
                "customer_id": customer_id,
                "category": category.value,
                "config": config,
            }
        )
        
        return instance
```

---

## 3. データフロー

### 3.1 カスタマーサポート質問の受け取り

```
外部インターフェース
├─ Web Chat Widget
├─ Email Support (incoming)
├─ Slack Integration
└─ API Endpoint

    ↓ normalize_question(question)

┌──────────────────────────────────────┐
│  SupportRequest                      │
├──────────────────────────────────────┤
│ request_id: UUID                     │
│ customer_id: int                     │
│ question: str                        │
│ source: str (web/email/slack/api)    │
│ received_at: datetime                │
│ customer_context: {                  │
│   plan: str,                         │
│   subscription_age_days: int,        │
│   previous_support_count: int,       │
│   company_size: str,                 │
│ }                                    │
│ conversation_history: List[Message]  │
│                                      │
└──────────────────────────────────────┘
```

### 3.2 質問分類のロジック

```
SupportRequest
    ↓
┌──────────────────────────────────────┐
│  QuestionClassifier.classify()       │
├──────────────────────────────────────┤
│                                      │
│ 1. Keyword Matching                  │
│    ├─ bug patterns                   │
│    ├─ faq patterns                   │
│    └─ escalation keywords            │
│                                      │
│ 2. NLU Intent Recognition (Claude)   │
│    ├─ extract entities               │
│    ├─ determine intent               │
│    └─ estimate confidence            │
│                                      │
│ 3. Context Analysis                  │
│    ├─ customer history               │
│    ├─ similar questions (KNN search) │
│    └─ time of day / urgency          │
│                                      │
│ 4. Confidence Scoring                │
│    └─ route if confidence >= 0.7     │
│                                      │
└──────────────────────────────────────┘
    ↓
ClassificationResult
├─ category: QuestionCategory
├─ confidence: float
├─ matched_rules: List[str]
├─ intent_details: dict
└─ recommended_action: str
```

### 3.3 自動応答の生成プロセス

```
ClassificationResult (confidence >= 0.7)
    ↓
┌──────────────────────────────────────┐
│  AutoResponder.generate_response()   │
├──────────────────────────────────────┤
│                                      │
│ 1. Template Selection                │
│    └─ find_template(category)        │
│       from template_service          │
│                                      │
│ 2. Knowledge Base Enrichment         │
│    ├─ faq_search(question)           │
│    ├─ doc_search(entities)           │
│    └─ best_practice_lookup()         │
│                                      │
│ 3. Context Enrichment                │
│    ├─ customer_plan                  │
│    ├─ applicable_features            │
│    └─ billing_info                   │
│                                      │
│ 4. Response Validation               │
│    ├─ completeness_check             │
│    ├─ factual_accuracy               │
│    └─ tone_analysis                  │
│                                      │
│ 5. Response Formatting               │
│    ├─ markdown_format                │
│    ├─ html_render (if UI)            │
│    └─ external_links                 │
│                                      │
└──────────────────────────────────────┘
    ↓
AutoResponse
├─ response_text: str
├─ confidence: float
├─ template_used: str
├─ knowledge_sources: List[str]
├─ external_links: List[Link]
└─ estimated_satisfaction: float
```

### 3.4 ユーザーエスカレーションのタイミング

```
分岐ポイント:

1. 分類時エスカレーション
   ├─ confidence < 0.7
   ├─ category in [escalate_*]
   └─ → 即座にEscalationHandler呼び出し

2. 応答生成時エスカレーション
   ├─ validation_failed
   ├─ required_context_missing
   └─ → 人間の判定を要請

3. 事後エスカレーション（フィードバックベース）
   ├─ customer_feedback: negative
   ├─ response_marked_unhelpful
   └─ → チケット再オープン

┌──────────────────────────────────────┐
│  EscalationHandler.escalate()        │
├──────────────────────────────────────┤
│                                      │
│ 1. Priority Determination            │
│    └─ set_sla_target()               │
│                                      │
│ 2. Team Routing                      │
│    ├─ identify_specialist()          │
│    └─ check_availability()           │
│                                      │
│ 3. Ticket Creation                   │
│    ├─ create_support_ticket()        │
│    ├─ set_initial_context()          │
│    └─ assign_agent()                 │
│                                      │
│ 4. User Notification                 │
│    ├─ send_email()                   │
│    ├─ display_ui_notification()      │
│    └─ provide_ticket_reference()     │
│                                      │
└──────────────────────────────────────┘
    ↓
SupportTicket (assigned to human agent)
```

---

## 4. 実装ロードマップ

### Phase 1: 質問分類拡張（2-3週間）

**目標**: ドメイン固有のサポート質問に対応する分類ロジック構築

**実装項目**:
1. QuestionCategory定義の拡張
   - 既存の4カテゴリ → 7カテゴリへ拡張
   - ファイル: `workflow/models/question_category.py`

2. NLU意図認識パイプライン
   - Claude API連携による意図抽出
   - 信頼度スコア計算
   - ファイル: `workflow/services/classifier_service.py`

3. キーワードベースルールシステム
   - バグ報告パターン定義
   - FAQ候補検出
   - ファイル: `workflow/validation/classification_rules.py`

4. コンテキスト分析モジュール
   - カスタマー企業規模別の優先度調整
   - 過去のサポート履歴との照合
   - ファイル: `workflow/services/context_analyzer.py`

5. テスト実装
   - 単体テスト: 100+ テストケース
   - ファイル: `tests/test_question_classifier.py` (拡張)

**成果物**:
- `QuestionCategory` enum定義
- `ClassifierService` クラス
- `classification_rules.yaml` ルール定義
- テストスイート（単体テスト+統合テスト）

**チェックポイント**:
- 実際の顧客質問データセット（最小100問）で検証
- 分類精度 >= 90%
- 処理時間 <= 1000ms

---

### Phase 2: 自動応答テンプレート構築（3-4週間）

**目標**: Wave25製品固有のFAQテンプレートライブラリ構築

**実装項目**:
1. テンプレート設計
   - カテゴリ別テンプレート設計（15-20個）
   - 変数埋め込み機構
   - ファイル: `workflow/models/response_template.py`

2. テンプレート管理システム
   - データベーステーブル設計（response_templates）
   - CRUD API実装
   - ファイル: `workflow/services/template_service.py` (拡張)

3. 自動応答生成エンジン
   - テンプレート選択ロジック
   - 変数埋め込み処理
   - 応答検証
   - ファイル: `workflow/services/response_generator.py`

4. ナレッジベース連携
   - FAQ検索API
   - ドキュメント検索統合
   - ファイル: `workflow/services/knowledge_base_service.py`

5. テンプレート実装例
   - API レート制限に関するFAQ
   - 認証・APIキー関連
   - 課金・プラン関連
   - 機能概要・ベストプラクティス

**成果物**:
- `ResponseTemplate` モデル
- テンプレートライブラリ（15-20個）
- `ResponseGenerator` クラス
- テンプレート検証テスト

**チェックポイント**:
- テンプレート自動応答での解決率 >= 70%
- カスタマー満足度スコア >= 4.0/5.0
- 応答生成時間 <= 500ms

---

### Phase 3: ナレッジベース連携（2-3週間）

**目標**: 既存ドキュメント・FAQとの統合

**実装項目**:
1. 知識源の統合
   - 公開ドキュメント (docs/)
   - 内部ナレッジベース
   - 関連ブログ記事
   - ファイル: `workflow/services/knowledge_integration.py`

2. 検索機構の実装
   - キーワード検索
   - セマンティック検索（ベクトル埋め込み）
   - ファイル: `workflow/services/semantic_search.py`

3. 関連リソース推奨
   - 質問に関連するドキュメント抽出
   - 外部リンク生成
   - ファイル: `workflow/services/resource_recommender.py`

4. ナレッジメトリクス
   - 検索クエリの記録
   - 回答の有用性スコア
   - ナレッジギャップ検出

**成果物**:
- `KnowledgeIntegrationService` クラス
- セマンティック検索インデックス
- 関連リソース推奨エンジン

**チェックポイント**:
- ナレッジベース検索精度 >= 80%
- 推奨リソースの有用性 >= 4.0/5.0

---

### Phase 4: パフォーマンス最適化・監視（2週間）

**目標**: 本番環境での安定稼働

**実装項目**:
1. パフォーマンス最適化
   - 分類・応答生成の並列化
   - キャッシング機構
   - ファイル: `workflow/cache/support_cache.py`

2. 監視・ロギング
   - API応答時間監視
   - エラーログ集約
   - メトリクスダッシュボード
   - ファイル: `workflow/monitoring/support_metrics.py`

3. 異常検知
   - エスカレーション率の異常値検知
   - 自動応答精度の劣化検知
   - ファイル: `workflow/monitoring/anomaly_detection.py`

4. 運用ダッシュボード
   - リアルタイムメトリクス表示
   - エージェント稼働状況
   - サポートチケット状態

**成果物**:
- キャッシング機構
- 監視スクリプト
- 運用ダッシュボード UI

**チェックポイント**:
- 処理時間: P99 <= 2000ms
- エラー率 < 0.1%
- 稼働率 >= 99.9%

---

## 5. テスト戦略

### 5.1 単体テスト

**QuestionClassifier 単体テスト**（existing pattern）:

```python
# tests/test_question_classifier_extended.py

def test_classify_auto_respond_faq():
    """FAQ対応可能な質問を自動応答に分類"""
    question = "API レート制限について教えてください"
    result = classifier.classify_question(question, {})
    assert result == "auto_respond"

def test_classify_escalate_security():
    """セキュリティ関連はエスカレーション"""
    question = "APIキーが漏洩した可能性があります"
    result = classifier.classify_question(question, {})
    assert result == "escalate_priority"

def test_confidence_score_too_low():
    """信頼度が低い場合は clarification_needed"""
    question = "あなたのサービスについて何か聞きたいことがあります"
    result, confidence = classifier.classify_question_with_score(question, {})
    assert result == "clarification_needed"
    assert confidence < 0.7

def test_context_based_routing():
    """企業規模でエスカレーション判定が変わる"""
    question = "割引について相談したいです"
    
    # SMB企業
    result_smb = classifier.classify_question(question, {
        "company_size": "small"
    })
    assert result_smb == "auto_respond"  # テンプレート応答
    
    # エンタープライズ
    result_ent = classifier.classify_question(question, {
        "company_size": "enterprise"
    })
    assert result_ent == "escalate_specialty"  # 営業へ
```

**AutoResponder 単体テスト**（existing pattern の拡張）:

```python
# tests/test_auto_responder_extended.py

def test_generate_response_with_knowledge():
    """ナレッジベースを使った応答生成"""
    question = "API レート制限は？"
    category = "auto_respond"
    context = {
        "customer_plan": "pro",
        "current_usage": 5000,  # per hour
    }
    
    response = responder.generate_response(question, category, context)
    assert response is not None
    assert "10,000" in response  # pro プランの制限値
    assert "プロプラン" in response
    assert "{{" not in response  # 変数が完全に埋め込まれている

def test_response_validation_fails():
    """検証失敗時はエスカレーション"""
    question = "セキュリティについて"
    category = "auto_respond"
    
    # 必要なコンテキストがない
    context = {}
    response = responder.generate_response(question, category, context)
    assert response is None  # 応答不可 → エスカレーション
```

### 5.2 統合テスト

**分類 → 応答 → エスカレーションフロー**:

```gherkin
# features/support_flow.feature

Feature: カスタマーサポート自動化フロー

Scenario: FAQ質問は自動応答される
  Given カスタマー "Acme Corp" が登録済み
  When 質問 "API レート制限について教えてください" を送信
  And システムが自動分類を実施
  Then 分類結果は "auto_respond"
  And 自動応答テンプレートが選択される
  And "10,000 requests/hour" を含む応答が生成される
  And 応答がカスタマーに配信される

Scenario: 高優先度バグはエスカレーション
  Given テストユーザー "test@acme.com" が登録済み
  When 質問 "データが全て削除されました" を送信
  And システムが自動分類を実施
  Then 分類結果は "escalate_priority"
  And SLA が 30 分に設定される
  And サポートチケットが自動生成される
  And チケット参照番号がカスタマーに通知される

Scenario: 不明確な質問は明確化を要求
  Given カスタマーが送信
  When 質問 "うまくいきません" を送信
  And システムが自動分類を実施
  Then 分類結果は "clarification_needed"
  And クラリフィケーション質問が返される
  例:
    """
    ご質問ありがとうございます。
    より詳しくお聞きして、正確にサポートさせていただきたいです。
    
    次の点を教えていただけますか？
    1. どの機能がうまくいきませんか？
    2. どのようなエラーメッセージが表示されますか？
    3. いつから発生していますか？
    """
```

### 5.3 E2E テスト

**カスタマーサポートダッシュボード経由**:

```python
# tests/e2e/test_support_dashboard.py

def test_e2e_support_workflow():
    """E2E: チャットから自動応答までの完全フロー"""
    
    # 1. ブラウザでダッシュボードにアクセス
    browser.navigate_to("http://localhost:8503/dashboard/support")
    
    # 2. チャットウィジェットで質問を送信
    chat_widget = browser.find_element("chat-input")
    chat_widget.send_keys("APIキーのリセット方法は？")
    browser.find_element("send-button").click()
    
    # 3. 自動応答が表示される
    response = browser.find_element("chat-response", timeout=5)
    assert "APIキーのリセット" in response.text
    assert "以下のステップに従ってください" in response.text
    
    # 4. リンクが機能する
    doc_link = response.find_element("a[href*='api-key']")
    assert doc_link.is_displayed()
    
    # 5. 顧客がフィードバックを送信
    feedback_button = browser.find_element("feedback-helpful")
    feedback_button.click()
    
    # 6. メトリクスが更新される
    metrics = browser.find_element("response-satisfaction-score")
    assert float(metrics.text) > 4.0

def test_e2e_escalation_flow():
    """E2E: エスカレーションフロー"""
    
    # セキュリティ問題を報告
    chat_widget = browser.find_element("chat-input")
    chat_widget.send_keys("セキュリティー脆弱性を発見しました")
    browser.find_element("send-button").click()
    
    # エスカレーション通知が表示される
    notification = browser.find_element("escalation-notification", timeout=5)
    assert "サポートチームにエスカレーション" in notification.text
    assert "チケット番号:" in notification.text
    
    # チケット番号をコピー可能
    ticket_number = notification.find_element("ticket-number").text
    assert ticket_number.startswith("TKT-")
```

---

## 6. デプロイ・運用

### 6.1 Wave25環境への展開方法

**デプロイメントパイプライン**:

```
Git Push (feature/wave25-support)
    ↓
CI Pipeline (GitHub Actions)
├─ 単体テスト実行
├─ 統合テスト実行
├─ E2E テスト実行
├─ コード品質チェック
└─ セキュリティスキャン
    ↓ (全て成功)
    ↓
ステージング環境デプロイ
├─ DBマイグレーション実行
├─ テンプレートライブラリ初期化
├─ ナレッジベースインデックス生成
└─ 統合テスト（ステージング）
    ↓ (問題なし)
    ↓
本番環境デプロイ（canary）
├─ トラフィック 5% をルーティング
├─ メトリクス監視（1時間）
└─ ヘルスチェック
    ↓ (正常)
    ↓
本番環境本デプロイ（100% トラフィック）
└─ デプロイ完了通知
```

**デプロイ設定ファイル** (`/.github/workflows/deploy-wave25-support.yml`):

```yaml
name: Deploy Wave25 Customer Support

on:
  push:
    branches: [feature/wave25-support, main]
    paths:
      - 'workflow/**'
      - 'dashboard/**'
      - 'tests/**'
      - '.github/workflows/deploy-*.yml'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run unit tests
        run: pytest tests/test_question_classifier*.py -v
      
      - name: Run integration tests
        run: pytest features/ -v
      
      - name: Run E2E tests (Playwright)
        run: pytest tests/e2e/ -v

  deploy-staging:
    needs: test
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to staging
        run: |
          ./scripts/deploy.sh staging
          ./scripts/run-migrations.sh staging

  deploy-prod:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v3
      - name: Deploy with canary (5%)
        run: ./scripts/deploy-canary.sh 5
      
      - name: Monitor canary (1 hour)
        run: ./scripts/monitor-canary.sh 3600
      
      - name: Promote to 100%
        run: ./scripts/deploy-full.sh
```

### 6.2 モニタリング・ログ管理

**監視メトリクス**:

```python
# workflow/monitoring/support_metrics.py

class SupportMetrics:
    """サポート部メトリクス収集"""
    
    # 分類関連
    classification_latency_ms = Histogram(
        "support_classification_latency_ms",
        "質問分類の処理時間",
        buckets=[100, 250, 500, 1000, 2000]
    )
    
    classification_distribution = Counter(
        "support_classification_total",
        "分類カテゴリ別の質問数",
        labels=["category"]
    )
    
    classification_confidence = Histogram(
        "support_classification_confidence",
        "分類の信頼度スコア",
        buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    )
    
    # 応答関連
    response_generation_latency_ms = Histogram(
        "support_response_latency_ms",
        "自動応答生成の処理時間",
        buckets=[100, 250, 500, 1000, 2000, 5000]
    )
    
    auto_response_rate = Gauge(
        "support_auto_response_rate",
        "自動応答できた割合（%）"
    )
    
    # エスカレーション関連
    escalation_rate = Gauge(
        "support_escalation_rate",
        "人間へエスカレーションした割合（%）"
    )
    
    escalation_sla_breach_rate = Gauge(
        "support_escalation_sla_breach_rate",
        "SLA違反率（%）"
    )
    
    # 顧客満足度
    customer_satisfaction_score = Histogram(
        "support_satisfaction_score",
        "カスタマー満足度スコア",
        buckets=[1, 2, 3, 4, 5]
    )
    
    # ナレッジベース
    knowledge_search_latency_ms = Histogram(
        "support_knowledge_search_latency_ms",
        "ナレッジベース検索時間",
        buckets=[50, 100, 250, 500, 1000]
    )
    
    knowledge_hit_rate = Gauge(
        "support_knowledge_hit_rate",
        "ナレッジベース検索ヒット率（%）"
    )
```

**ログ管理戦略**:

```
Application Logs
├─ Classifier Logs
│  ├─ classification_request: {question, category, confidence}
│  ├─ classification_error: {error_message, traceback}
│  └─ classification_audit: {timestamp, category, user_id}
│
├─ Responder Logs
│  ├─ response_generated: {template_used, variables_substituted}
│  ├─ response_validation_failed: {reason, fallback_action}
│  └─ response_delivered: {delivery_channel, timestamp}
│
├─ Escalation Logs
│  ├─ escalation_triggered: {reason, priority, assigned_team}
│  ├─ ticket_created: {ticket_id, sla_minutes}
│  └─ ticket_assigned: {agent_id, timestamp}
│
└─ Error Logs
   ├─ api_errors: {status_code, endpoint, error_message}
   ├─ db_errors: {query, error_message, affected_rows}
   └─ external_service_errors: {service, error, retry_attempt}

集約先: CloudWatch / Datadog / Splunk
保持期間: 90 日（本番）, 30 日（ステージング）
```

### 6.3 ローテーション・スケーリング戦略

**リソース管理**:

```
┌────────────────────────────────────────────┐
│   Support Agent Auto-Scaling Configuration │
├────────────────────────────────────────────┤
│                                            │
│ Min Replicas: 2                            │
│ Max Replicas: 10                           │
│                                            │
│ Scaling Triggers:                          │
│ ├─ CPU Utilization: > 70% ← scale up      │
│ ├─ Memory Usage: > 80% ← scale up         │
│ ├─ Queue Length (escalations): > 50       │
│ │  ← add manual support agents            │
│ └─ Response Latency P99: > 2s ← scale up  │
│                                            │
│ Scale-Down Cooldown: 300 seconds           │
│                                            │
└────────────────────────────────────────────┘
```

**エージェント ローテーションポリシー**:

```
定期ローテーション（24時間ごと）
├─ 00:00 - 08:00 UTC: Asia-Pacific shift
├─ 08:00 - 16:00 UTC: Europe-Middle East shift
└─ 16:00 - 24:00 UTC: Americas shift

スケーリング判定（毎5分）
├─ escalation_queue.length > 50
│  → シニアサポート層を追加起動
├─ response_quality_score < 3.5/5
│  → スペシャリストをリクエスト
└─ customer_satisfaction < 4.0
   → チーム lead にアラート
```

**負荷分散**:

```
Incoming Support Request
    ↓
┌─────────────────────────────────────┐
│  Load Balancer                      │
├─────────────────────────────────────┤
│ - Round-robin                       │
│ - Least connections                 │
│ - Weighted (priority-based)         │
└────────┬────────────────────────────┘
         │
    ┌────┴────┬────────────────┐
    ↓         ↓                ↓
┌────────┐ ┌────────┐ ┌────────┐
│ Agent1 │ │ Agent2 │ │ Agent3 │
│ (busy) │ │(idle)  │ │ (idle) │
└────────┘ └────────┘ └────────┘
           →(route)

動的ルーティング:
├─ Agent Utilization < 50% → route
├─ Agent Availability = true → route
└─ Agent Specialization match → boost score
```

---

## 7. リスク管理と運用フォールバック

### 7.1 リスク評価

| リスク | 発生可能性 | 影響度 | 対応策 |
|--------|-----------|--------|--------|
| **分類精度低下** | 中 | 高 | 信頼度閾値引上げ→エスカレーション率向上 |
| **ナレッジベース古い情報** | 中 | 中 | 定期同期 + バージョン管理 |
| **Claude API 割当枯渇** | 低 | 中 | キューイング + フォールバック対応 |
| **エスカレーション遅延** | 低 | 高 | SLA 監視 + アラート |
| **データプライバシー漏洩** | 低 | 最高 | PII マスキング + 暗号化 |

### 7.2 フォールバック戦略

```
Question Classification Failed
    ↓
[Retry Logic]
├─ Retry 1: キャッシュから分類結果を取得
├─ Retry 2: 簡易的なキーワードマッチに戻す
└─ Retry 3: 無条件に "escalate" (人間へ)

Auto Response Generation Failed
    ↓
[Fallback Response]
├─ Templated Response: 「申し訳ございません...」
├─ Support Channel: メールアドレス・チャットリンク提供
└─ Escalation: チケット自動生成

Knowledge Base Unavailable
    ↓
[Graceful Degradation]
├─ In-Memory Cache から応答
├─ Generic Template を返す
└─ Escalation へ自動転換
```

---

## 8. まとめと次ステップ

### 実装検査リスト

- [ ] Phase 1: 質問分類拡張（Week 1-3）
- [ ] Phase 2: 自動応答テンプレート（Week 3-6）
- [ ] Phase 3: ナレッジベース連携（Week 6-9）
- [ ] Phase 4: パフォーマンス最適化（Week 9-10）
- [ ] ステージング環境での統合テスト（Week 10）
- [ ] 本番環境デプロイ（Week 11）

### 成功指標

**Phase 1-4 完了時点での目標値**:

| 指標 | 目標値 | 測定方法 |
|------|--------|---------|
| **自動応答率** | >= 70% | escalation_count / total_requests |
| **カスタマー満足度** | >= 4.0/5.0 | 自動応答後のアンケート平均値 |
| **処理時間（P99）** | <= 2000ms | メトリクス監視 |
| **分類精度** | >= 90% | テストデータセット評価 |
| **SLA達成率** | >= 99% | エスカレーションチケット監視 |
| **システム稼働率** | >= 99.9% | インフラメトリクス |

---

## 付録: 関連ファイルリスト

**既存実装**:
- `/tests/test_question_classifier.py` - 質問分類ロジック
- `/tests/test_auto_responder.py` - 自動応答ロジック
- `/dashboard/blueprints.py` - テンプレート管理API
- `/workflow/db_schema.py` - ワークフロースキーマ

**関連設計ドキュメント**:
- `DESIGN_2784_DEPARTMENT_DEPLOY.md` - 部署デプロイ設計
- `API_DESIGN_2485.md` - API スキーマ設計
- `IMPLEMENTATION_GUIDE_2485.md` - 実装ガイド

**新規実装ファイル（Phase別）**:

*Phase 1*:
- `workflow/models/question_category.py`
- `workflow/services/classifier_service.py`
- `workflow/validation/classification_rules.py`
- `workflow/services/context_analyzer.py`
- `tests/test_question_classifier_extended.py`

*Phase 2*:
- `workflow/models/response_template.py`
- `workflow/services/response_generator.py`
- `workflow/models/support_response.py`
- `tests/test_auto_responder_extended.py`

*Phase 3*:
- `workflow/services/knowledge_base_service.py`
- `workflow/services/semantic_search.py`
- `workflow/services/resource_recommender.py`

*Phase 4*:
- `workflow/cache/support_cache.py`
- `workflow/monitoring/support_metrics.py`
- `workflow/monitoring/anomaly_detection.py`
- `dashboard/static/support-dashboard.html`
- `dashboard/static/support-dashboard.js`

---

**作成者**: AI Code Assistant  
**最終更新**: 2026-04-30  
**次回レビュー**: Phase 1 完了後
