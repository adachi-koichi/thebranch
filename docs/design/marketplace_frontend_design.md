# AIエージェント マーケットプレイス フロントエンド設計

**Document Version**: 1.0  
**Created**: 2026-04-26  
**Related Task**: #2494 Tech Lead: AIエージェントマーケットプレイス設計  
**Related Docs**: `marketplace_db_schema.md`, `marketplace_api_design.md`

---

## 1. 概要

THEBRANCH マーケットプレイスのフロントエンド UI/UX 設計。2つのメイン画面で検索・インストール機能を提供します。

### ページ構成

1. **マーケットプレイス一覧ページ** (`/marketplace`)
   - エージェント検索・フィルター・ソート・ページネーション
   - カテゴリ別ナビゲーション

2. **エージェント詳細ページ** (`/marketplace/agents/{id}`)
   - エージェント詳細情報
   - 機能・レビュー表示
   - インストールボタン

### 技術スタック

- **フロントエンド**: HTML + CSS + JavaScript（Vanilla）
- **API**: Flask (`/api/marketplace/*`)
- **参考**: `dashboard/index.html`, `dashboard/js/scores.js`

---

## 2. マーケットプレイス一覧ページ

### 2.1 ページレイアウト

```
┌─────────────────────────────────────────────────────────┐
│ THEBRANCH マーケットプレイス                              │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐ │
│  │ 検索ボックス [                  🔍] 並び替え: [▼]   │ │
│  └─────────────────────────────────────────────────────┘ │
├──────────────────┬──────────────────────────────────────┤
│ フィルター:      │ エージェント一覧                    │
│                  │                                      │
│ ☑ 全て           │ ┌──────────────┐ ┌──────────────┐  │
│ ○ HR             │ │              │ │              │  │
│ ○ Finance        │ │ タスク管理    │ │ データ分析   │  │
│ ○ Marketing      │ │ ⭐⭐⭐⭐⭐  │ │ ⭐⭐⭐⭐   │  │
│ ○ Sales          │ │ (234 installs)│ │(156 installs)│  │
│ ○ Engineering    │ │              │ │              │  │
│ ○ Support        │ │ [インストール] │ │[インストール] │  │
│                  │ └──────────────┘ └──────────────┘  │
│ 評価:            │                                      │
│ ☐ 4.0 以上       │ ┌──────────────┐ ┌──────────────┐  │
│ ☐ 3.5 以上       │ │              │ │              │  │
│                  │ │ 報告書作成    │ │ スケジューリング│
│                  │ │ ⭐⭐⭐⭐   │ │ ⭐⭐⭐⭐⭐ │  │
│                  │ │(89 installs) │ │(412 installs)│  │
│                  │ │              │ │              │  │
│                  │ │ [インストール] │ │[インストール] │  │
│                  │ └──────────────┘ └──────────────┘  │
│                  │                                      │
│                  │ < 1 2 3 4 5 ... 12 >               │
├──────────────────┴──────────────────────────────────────┤
│ © 2026 THEBRANCH - All rights reserved                 │
└─────────────────────────────────────────────────────────┘
```

### 2.2 コンポーネント詳細

#### 2.2.1 検索・ソート セクション

```html
<div class="marketplace-header">
  <h1>🤖 AIエージェント マーケットプレイス</h1>
  
  <div class="search-sort-area">
    <div class="search-box">
      <input 
        type="text" 
        id="searchInput" 
        placeholder="エージェントを検索..." 
        class="search-input"
      />
      <button class="search-btn">🔍</button>
    </div>
    
    <select id="sortSelect" class="sort-select">
      <option value="score">評価が高い順</option>
      <option value="rating">レーティング順</option>
      <option value="installation_count">人気順</option>
      <option value="created_at">新着順</option>
    </select>
  </div>
</div>
```

**機能**:
- **検索**: キーストローク検索（debounce 300ms）→ API 呼び出し
- **ソート**: score, rating, installation_count, created_at に対応
- **自動ページネーションリセット**: 検索時は page=1 にリセット

#### 2.2.2 左側フィルター パネル

```html
<aside class="filters-panel">
  <h3>フィルター</h3>
  
  <!-- カテゴリフィルター -->
  <div class="filter-group">
    <label class="filter-title">
      <input type="checkbox" id="catAll" checked />
      全て
    </label>
    <div class="category-list">
      <label class="filter-item">
        <input type="checkbox" class="category-filter" value="hr" />
        HR
      </label>
      <label class="filter-item">
        <input type="checkbox" class="category-filter" value="finance" />
        Finance
      </label>
      <label class="filter-item">
        <input type="checkbox" class="category-filter" value="marketing" />
        Marketing
      </label>
      <!-- 他のカテゴリ... -->
    </div>
  </div>
  
  <!-- 評価フィルター -->
  <div class="filter-group">
    <h4>評価</h4>
    <label class="filter-item">
      <input type="checkbox" class="rating-filter" value="4.0" />
      4.0 以上 ⭐⭐⭐⭐
    </label>
    <label class="filter-item">
      <input type="checkbox" class="rating-filter" value="3.5" />
      3.5 以上 ⭐⭐⭐
    </label>
  </div>
</aside>
```

**機能**:
- **複数カテゴリ選択**: チェックボックスで複数選択可能
- **評価フィルター**: min_rating パラメータで API フィルター
- **フィルター状態保持**: URL query parameter に状態を保存

#### 2.2.3 エージェント カード

```html
<div class="agent-card">
  <div class="agent-card-header">
    <img src="{icon_url}" class="agent-icon" />
    <div class="agent-title">
      <h3>{name}</h3>
      <p class="agent-category">{category.name}</p>
    </div>
  </div>
  
  <p class="agent-description">{description}</p>
  
  <div class="agent-stats">
    <div class="stat">
      <span class="stat-label">評価</span>
      <span class="stat-value">⭐ {rating}/5 ({review_count}件)</span>
    </div>
    <div class="stat">
      <span class="stat-label">インストール</span>
      <span class="stat-value">{installation_count}</span>
    </div>
  </div>
  
  <div class="agent-tags">
    {tags.map(tag => <span class="tag">{tag}</span>)}
  </div>
  
  <div class="agent-actions">
    <a href="/marketplace/agents/{id}" class="btn-view">詳細を見る</a>
    <button class="btn-install" onclick="installAgent('{id}')">
      インストール
    </button>
  </div>
</div>
```

**デザイン**:
- **カード形式**: グリッドレイアウト（3 カラム / 2 カラム / 1 カラム）
- **情報密度**: 名前、説明、評価、インストール数、タグを表示
- **アクション**: 「詳細を見る」「インストール」ボタン

#### 2.2.4 ページネーション

```html
<div class="pagination">
  <button id="prevBtn" class="pag-btn" onclick="prevPage()">← 前へ</button>
  <div class="page-numbers">
    <button class="page-number active" onclick="goToPage(1)">1</button>
    <button class="page-number" onclick="goToPage(2)">2</button>
    <button class="page-number" onclick="goToPage(3)">3</button>
    <span class="page-ellipsis">...</span>
    <button class="page-number" onclick="goToPage({total_pages})">
      {total_pages}
    </button>
  </div>
  <button id="nextBtn" class="pag-btn" onclick="nextPage()">次へ →</button>
  <span class="page-info">
    ページ {page} / {total_pages} （全 {total_count} 件）
  </span>
</div>
```

---

## 3. エージェント詳細ページ

### 3.1 ページレイアウト

```
┌─────────────────────────────────────────────────────────┐
│ ← 戻る                                     🔗 💬 ⭐ 📋  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [バナー画像                              ]               │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 🎯 HR Task Automation                  ⭐4.5 (42件)  ││
│  │ v1.2.0 | 234 installs | HR                          ││
│  │                                                      ││
│  │ Publisher: hr_team                                  ││
│  │                                                      ││
│  │ このエージェントは、人事タスクを自動化し...           ││
│  │                                                      ││
│  │ [インストール] [ドキュメント]                         ││
│  └─────────────────────────────────────────────────────┘│
├──────────────────┬──────────────────────────────────────┤
│ 機能一覧:        │ 詳細情報                             │
│                  │                                      │
│ ✓ 自動タスク割当 │ 説明:                                │
│ ✓ 承認フロー     │ {detailed_description}               │
│ ✓ レポート生成   │                                      │
│                  │ 必要要件:                            │
│ スキル:          │ - Python 3.9+                        │
│ ・task_schedul   │ - Flask 2.0+                         │
│ ・approval_wf    │ - Storage: 256MB                     │
│ ・reporting      │                                      │
│                  │ リンク:                              │
│                  │ 📚 ドキュメント                      │
│                  │ 💻 GitHub                           │
│                  │ 🤝 サポート                          │
│                  │                                      │
│                  │ リリース:                            │
│                  │ • v1.2.0 (2026-04-20) [アクティブ]  │
│                  │ • v1.1.0 (2026-03-15) [アクティブ]  │
│                  │                                      │
├──────────────────┴──────────────────────────────────────┤
│ レビュー (42件)                                          │
│                                                          │
│ ⭐⭐⭐⭐⭐ ユーザーA (2026-04-20)                      │
│ 「素晴らしいエージェント」                                │
│ タスク割り当てが本当に効率的です                        │
│                                                          │
│ ⭐⭐⭐⭐ ユーザーB (2026-04-15)                      │
│ 「ほぼ完璧」                                            │
│ Slack 連携があるともっと良い                           │
│                                                          │
│ < レビュー一覧を見る >                                   │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ © 2026 THEBRANCH                                        │
└─────────────────────────────────────────────────────────┘
```

### 3.2 コンポーネント詳細

#### 3.2.1 ヘッダー セクション

```html
<div class="detail-header">
  <button class="btn-back" onclick="history.back()">← 戻る</button>
  <div class="header-actions">
    <button class="btn-icon" title="外部リンク">🔗</button>
    <button class="btn-icon" title="シェア">💬</button>
    <button class="btn-icon" title="お気に入り">⭐</button>
    <button class="btn-icon" title="レポート">📋</button>
  </div>
</div>
```

#### 3.2.2 バナー・タイトル セクション

```html
<div class="detail-banner">
  <img src="{agent.banner_url}" class="banner-image" />
</div>

<div class="detail-title-section">
  <img src="{agent.icon_url}" class="detail-icon" />
  <div class="title-content">
    <h1>{agent.name}</h1>
    <div class="meta-info">
      <span class="version">v{agent.version}</span>
      <span class="separator">|</span>
      <span class="installs">{agent.installation_count} installs</span>
      <span class="separator">|</span>
      <span class="category">{agent.category.name}</span>
    </div>
    <p class="publisher">
      Publisher: <strong>{agent.publisher.username}</strong>
    </p>
    <div class="rating">
      <span class="stars">⭐ {agent.rating}/5</span>
      <span class="reviews">({agent.review_count} レビュー)</span>
    </div>
  </div>
  
  <div class="action-buttons">
    <button class="btn-install" onclick="showInstallModal('{agent.id}')">
      インストール
    </button>
    <a href="{agent.documentation_url}" class="btn-secondary">
      ドキュメント
    </a>
  </div>
</div>
```

#### 3.2.3 説明・機能 セクション

```html
<div class="detail-content">
  <div class="content-main">
    <h2>説明</h2>
    <div class="description-text">
      {agent.detailed_description}
    </div>
  </div>
  
  <aside class="content-sidebar">
    <h3>機能</h3>
    <ul class="features-list">
      {agent.features.map(feature => (
        <li class="feature-item">
          <img src="{feature.icon_url}" class="feature-icon" />
          <div>
            <strong>{feature.name}</strong>
            <p>{feature.description}</p>
          </div>
        </li>
      ))}
    </ul>
    
    <h3>スキル</h3>
    <ul class="skills-list">
      {agent.capabilities.map(cap => (
        <li class="skill-item">✓ {cap.name}</li>
      ))}
    </ul>
    
    <h3>要件</h3>
    <ul class="requirements-list">
      {Object.entries(agent.requirements).map(([key, value]) => (
        <li>{key}: {value}</li>
      ))}
    </ul>
    
    <h3>リンク</h3>
    <div class="links-list">
      <a href="{agent.documentation_url}" class="link-item">
        📚 ドキュメント
      </a>
      <a href="{agent.github_url}" class="link-item">
        💻 GitHub
      </a>
      <a href="{agent.support_url}" class="link-item">
        🤝 サポート
      </a>
    </div>
    
    <h3>リリース</h3>
    <div class="releases-list">
      {agent.releases.map(release => (
        <div class="release-item">
          <span class="release-version">v{release.version}</span>
          <span class="release-date">{release.published_at}</span>
          <span class="release-status">[{release.status}]</span>
          <p>{release.release_notes}</p>
        </div>
      ))}
    </div>
  </aside>
</div>
```

#### 3.2.4 レビュー セクション

```html
<div class="reviews-section">
  <h2>レビュー</h2>
  
  <div class="reviews-list">
    {agent.recent_reviews.map(review => (
      <div class="review-item">
        <div class="review-header">
          <div class="reviewer-info">
            <strong>{review.user.username}</strong>
            <span class="review-date">{review.created_at}</span>
          </div>
          <div class="review-rating">
            {Array(review.rating).fill('⭐').join('')}
          </div>
        </div>
        <h4 class="review-title">{review.title}</h4>
        <p class="review-comment">{review.comment}</p>
        <button class="btn-helpful">👍 役に立つ ({review.helpful_count})</button>
      </div>
    ))}
  </div>
  
  <a href="/marketplace/agents/{agent.id}/reviews" class="link-more">
    全てのレビューを見る →
  </a>
</div>
```

---

## 4. インストール モーダル

```html
<div class="modal-overlay" id="installModal">
  <div class="modal-content">
    <h2>エージェントをインストール</h2>
    <p class="agent-name">{agent.name}</p>
    
    <div class="install-form">
      <div class="form-group">
        <label>バージョン</label>
        <select id="versionSelect">
          <option value="1.2.0">v1.2.0 (最新)</option>
          <option value="1.1.0">v1.1.0</option>
        </select>
      </div>
      
      <!-- settings_schema に基づいて動的生成 -->
      <div id="settingsForm">
        <!-- ここに動的フォームを生成 -->
      </div>
      
      <div class="form-actions">
        <button class="btn-cancel" onclick="closeInstallModal()">
          キャンセル
        </button>
        <button class="btn-confirm" onclick="submitInstall()">
          インストール
        </button>
      </div>
    </div>
  </div>
</div>
```

**機能**:
- **バージョン選択**: agent.releases から選択可能
- **動的フォーム**: settings_schema に基づいてフォーム自動生成
- **検証**: API 側で 422 エラーの場合、エラーメッセージを表示

---

## 5. 実装パターン

### 5.1 JavaScript 実装例

```javascript
// dashboard/js/marketplace.js

class Marketplace {
  constructor() {
    this.currentPage = 1;
    this.currentSort = 'score';
    this.currentFilters = {};
    this.debounceTimer = null;
  }
  
  // 一覧取得
  async loadAgents() {
    const params = {
      page: this.currentPage,
      sort: this.currentSort,
      ...this.currentFilters
    };
    
    const response = await fetch(
      `/api/marketplace/agents?${new URLSearchParams(params)}`,
      {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      }
    );
    
    const data = await response.json();
    this.renderAgentsList(data.data.agents, data.data.pagination);
  }
  
  // 検索（debounce）
  onSearchInput(query) {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.currentFilters.search = query;
      this.currentPage = 1;
      this.loadAgents();
    }, 300);
  }
  
  // 詳細取得
  async loadAgentDetail(agentId) {
    const response = await fetch(`/api/marketplace/agents/${agentId}`, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    
    const data = await response.json();
    this.renderAgentDetail(data.data.agent);
  }
  
  // インストール
  async installAgent(agentId, configuration) {
    const response = await fetch(
      `/api/marketplace/agents/${agentId}/install`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          organization_id: getCurrentOrgId(),
          configuration: configuration
        })
      }
    );
    
    if (response.ok) {
      showSuccessMessage('インストール完了しました');
      closeInstallModal();
    } else {
      const error = await response.json();
      showErrorMessage(error.error.message);
    }
  }
}
```

### 5.2 CSS グリッドレイアウト

```css
.marketplace-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
  padding: 20px;
}

@media (max-width: 1024px) {
  .marketplace-grid {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  }
}

@media (max-width: 768px) {
  .marketplace-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  }
}
```

---

## 6. アクセシビリティ

- ✅ ARIA ラベル対応
- ✅ キーボードナビゲーション（Tab キー）
- ✅ スクリーンリーダー対応
- ✅ コントラスト比 4.5:1 以上

---

## 7. 実装チェックリスト

### 一覧ページ
- [ ] 検索ボックス実装
- [ ] カテゴリフィルター実装
- [ ] 評価フィルター実装
- [ ] ソート機能実装
- [ ] エージェント カード実装
- [ ] ページネーション実装
- [ ] レスポンシブデザイン対応

### 詳細ページ
- [ ] バナー・タイトル表示
- [ ] 説明表示
- [ ] 機能一覧表示
- [ ] スキル一覧表示
- [ ] リンク表示
- [ ] リリース履歴表示
- [ ] レビュー表示
- [ ] インストールボタン実装
- [ ] インストールモーダル実装
- [ ] 動的フォーム生成（settings_schema）

### 共通
- [ ] 認証トークン处理
- [ ] エラーハンドリング（404, 422等）
- [ ] ローディング表示
- [ ] レート制限対応
- [ ] キャッシング実装

---

## 8. 次フェーズ

**Backend 実装**: `dashboard/marketplace_routes.py`
- DB Migration（マイグレーション）
- API エンドポイント実装
- FTS5 検索実装

**Frontend 実装**: `dashboard/js/marketplace.js` + `dashboard/marketplace.html`
- UI コンポーネント実装
- API 統合
- ブラウザ確認
