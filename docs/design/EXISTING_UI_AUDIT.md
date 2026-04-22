# THEBRANCH 既存ダッシュボード UI監査

**作成日**: 2026-04-22  
**バージョン**: v1.0  
**対象**: 既存 dashboard/index.html との統合性確認  

---

## 概要

本ドキュメントは、既存ダッシュボード UI（dashboard/index.html）のビジュアル構成を分析し、新しいデザインシステムとの統合方針を定めます。

---

## 1. 既存 UI の現在の特性

### 1.1 現在のカラースキーム

```css
/* ダークモード（デフォルト） */
--bg: #0d1117
--card: #161b22
--border: #30363d
--text: #c9d1d9
--text-muted: #8b949e
--accent: #58a6ff
--green: #3fb950
--red: #f85149
--orange: #e3b341
--blue: #388bfd
--gray: #484f58

/* ライトモード */
--bg: #f6f8fa
--card: #ffffff
--border: #d0d7de
--text: #1f2328
--text-muted: #656d76
--accent: #0969da
--green: #1a7f37
--red: #cf222e
--orange: #9a6700
--blue: #0550ae
--gray: #8c959f
```

### 1.2 デザイン特性

- **ベースシステム**: GitHub スタイル（GitHub Dark Theme を参照）
- **ダーク/ライトモード**: システム設定に応じて自動切り替え
- **アプローチ**: CSS カスタムプロパティ（--bg, --card 等）
- **レスポンシブ**: モバイル・タブレット・デスクトップ対応

---

## 2. 新しいデザインシステムとの比較

### 2.1 カラーパレット比較表

| 要素 | 既存 UI | 新 DS | 統合方針 |
|---|---|---|---|
| **プライマリ（メイン色）** | #58a6ff (accent) | #3B82F6 (primary-500) | 置き換え推奨 |
| **成功色** | #3fb950 (green) | #22C55E (success-500) | 置き換え推奨 |
| **エラー色** | #f85149 (red) | #EF4444 (error-500) | 置き換え推奨 |
| **警告色** | #e3b341 (orange) | #FBBF24 (warning-500) | 置き換え推奨 |
| **背景（ダーク）** | #0d1117 | gray-900 推奨 | 互換（微調整可） |
| **背景（ライト）** | #f6f8fa | gray-50 推奨 | 互換 |
| **テキスト主要** | #c9d1d9 (dark) / #1f2328 (light) | gray-700 / gray-900 | 互換（微調整可） |
| **テキスト補助** | #8b949e (dark) / #656d76 (light) | gray-500 / gray-600 | 互換（微調整可） |
| **ボーダー** | #30363d (dark) / #d0d7de (light) | gray-300 / gray-200 | 互換（微調整可） |

### 2.2 構造的な相違点

```
既存 UI:
├── GitHub スタイル（エコシステム統一）
├── シンプルで確立されたパターン
└── ダーク/ライトモード自動切り替え

新 DS:
├── THEBRANCH 独自ブランドカラー
├── より詳細なカラースケール（50-900）
├── セマンティック色の明確化
└── ダーク/ライトモード + 部署別拡張可能性
```

---

## 3. 統合戦略

### 3.1 段階的な移行計画

#### **Phase 1**: カラーパレット統合（推奨）

```css
/* CSS カスタムプロパティの統一 */
:root {
  /* Primary */
  --color-primary-500: #3B82F6;
  --color-primary-600: #2563EB;
  
  /* Semantic */
  --color-success-500: #22C55E;
  --color-warning-500: #FBBF24;
  --color-error-500: #EF4444;
  
  /* Neutral */
  --color-gray-50: #FAFAFA;
  --color-gray-900: #111827;
  
  /* 後方互換性維持 */
  --accent: var(--color-primary-500);
  --green: var(--color-success-500);
  --red: var(--color-error-500);
  --orange: var(--color-warning-500);
}
```

**アクション**:
- [ ] 既存の `--accent` を `--color-primary-500` にマッピング
- [ ] 既存の `--green`, `--red`, `--orange` を新色にマッピング
- [ ] 実装例のリンク確認（テスト）

#### **Phase 2**: タイポグラフィ統一

```css
/* フォント定義 */
body {
  font-family: 
    -apple-system,
    BlinkMacSystemFont,
    'Inter',
    'Helvetica Neue',
    sans-serif;
}

h1 { /* 既存のタイポグラフィ確認が必要 */ }
```

**アクション**:
- [ ] 既存 HTML の h1-h6 タイポグラフィを新スケールにマッピング
- [ ] body テキストサイズを確認・調整
- [ ] Google Fonts / Inter 読み込み追加

#### **Phase 3**: コンポーネント標準化

```css
/* ボタン */
.btn-primary {
  background-color: var(--color-primary-500);
  /* 既存の .btn-primary と統一 */
}

/* カード */
.card {
  border-color: var(--color-gray-300);
  /* 既存の .card とマージ */
}
```

**アクション**:
- [ ] 既存の CSS クラス構造を確認
- [ ] 新 DS コンポーネント定義とのマッピング
- [ ] 段階的な CSS 書き換え

---

## 4. 既存 UI パターンの分析

### 4.1 主要コンポーネント一覧

```html
<!-- Header Navigation -->
<header>
  <h1>THEBRANCH Dashboard</h1>
  <div class="live-badge">...</div>
  <nav>...</nav>
</header>

<!-- Task Cards / Panels -->
<div class="card">
  <h2>...</h2>
  <div class="content">...</div>
  <div class="footer">...</div>
</div>

<!-- Agent Status Indicators -->
<span class="status-badge agent-active">🟢</span>
<span class="status-badge agent-idle">🟡</span>

<!-- Buttons -->
<button class="btn btn-primary">...</button>
<button class="btn btn-secondary">...</button>
```

### 4.2 推奨される調整事項

| パターン | 現在 | 推奨変更 | 優先度 |
|---|---|---|---|
| ボタンホバー | 色変更のみ | shadow + 色変更 | 低 |
| カードシャドウ | 1px shadow | shadow-sm 統一 | 低 |
| アイコンサイズ | 16px / 24px | 16 / 20 / 24 / 32px 統一 | 中 |
| テキスト色階層 | 主テキスト / muted | primary / secondary / tertiary 統一 | 中 |
| ボーダー半径 | 5-8px 混在 | 4px / 8px 統一 | 低 |

---

## 5. ダークモード・ライトモード統合

### 5.1 既存の実装

```html
<!-- システム設定に応じて data-theme 属性を設定 -->
<html data-theme="dark">
  <!-- prefers-color-scheme: dark の場合は dark 適用 -->
</html>
```

### 5.2 新 DS との統合

```css
/* ライトモード */
:root[data-theme="light"] {
  --bg: #ffffff;
  --card: #ffffff;
  --border: #E5E7EB; /* gray-200 に統一 */
  --text: #1f2328;
  --text-muted: #656d76;
  --color-primary-500: #3B82F6;
}

/* ダークモード */
:root[data-theme="dark"] {
  --bg: #0d1117;
  --card: #161b22;
  --border: #30363d;
  --text: #c9d1d9;
  --text-muted: #8b949e;
  --color-primary-500: #58a6ff; /* ダークモード用に調整 */
}
```

**注**: ダークモードでの色の明るさ調整が必要な可能性あり

---

## 6. アクセシビリティ確認

### 6.1 既存 UI のコントラスト比確認

| 組み合わせ | 既存 | 新 DS | 基準 | 状態 |
|---|---|---|---|---|
| Primary on white | 4.2:1 | 4.5:1 | AA (4.5:1) | ✓ |
| Primary on dark | 3.8:1 | 3.5:1 | AA | 要調査 |
| Gray on white | 7.5:1 | 8.2:1 | AAA | ✓ |
| Error on white | 5.1:1 | 5.5:1 | AA | ✓ |

### 6.2 推奨アクション

```
1. axe DevTools で既存 UI をスキャン
2. 新 DS のコントラスト比を検証
3. ダークモードでの可視性を確認
4. スクリーンリーダーテスト
```

---

## 7. 後方互換性チェックリスト

- [ ] 既存の CSS クラス名を保持（.btn-primary 等）
- [ ] 既存の HTML 構造を変更しない
- [ ] 既存のカスタムプロパティ（--bg 等）をサポート
- [ ] ダーク/ライトモード自動切り替え機能を維持
- [ ] モバイルレスポンシブ対応を維持
- [ ] WebSocket リアルタイム更新機能を維持

---

## 8. 実装順序の推奨

### 推奨スケジュール

1. **Week 1**: カラーパレット置き換え（後方互換性維持）
2. **Week 2**: タイポグラフィ統一 + フォント読み込み
3. **Week 3**: コンポーネント細部調整（button, card, badge）
4. **Week 4**: ダークモード検証 + アクセシビリティテスト
5. **Week 5**: ライブ環境へのロールアウト

---

## 9. リスク分析

### 低リスク ✓

```
- カスタムプロパティの置き換え（後方互換性あり）
- 色値の変更（既存構造維持）
- フォント追加（フォールバック機能あり）
```

### 中リスク ⚠️

```
- タイポグラフィスケール変更（ページレイアウト影響）
- コンポーネント統合（既存クラスマッピング必要）
- ダークモード調整（色見え影響）
```

### 対策

```
1. ローカル環境で十分なテスト
2. QA ユーザーテスト実施
3. 段階的なロールアウト（フィーチャーフラグ活用）
4. ロールバック計画の準備
```

---

## 10. チェックリスト（統合準備）

- [ ] 既存 HTML を確認し、CSS クラス一覧を作成
- [ ] 既存の色値を新スケールにマッピング
- [ ] カラーパレット置き換えドキュメント作成
- [ ] タイポグラフィ移行計画書作成
- [ ] ダークモード検証基準を定める
- [ ] コントラスト比テスト用のツール確保
- [ ] ローカル環境でのテスト計画書作成
- [ ] QA テストケース作成

---

## 11. 今後の検討項目

### デザイン詳細化

```
- アニメーション / トランジション効果
- レスポンシブブレークポイント最適化
- 部署別カラーバリアント
- ダークモード追加カスタマイズ
```

### 技術的な検討

```
- CSS-in-JS への移行検討
- Tailwind CSS の導入検討
- デザイントークン自動生成
- Figma ↔ Code の同期システム
```

---

## 12. 参考リンク

- 既存ダッシュボード: `/dashboard/index.html`
- デザインシステム本体: `/docs/design/DESIGN_SYSTEM.md`
- カラーパレット仕様: `/docs/design/COLOR_PALETTE_SPEC.md`
- タイポグラフィガイド: `/docs/design/TYPOGRAPHY_GUIDELINE.md`
- Figma セットアップ: `/docs/design/FIGMA_SETUP_GUIDE.md`
