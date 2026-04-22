# THEBRANCH タイポグラフィガイドライン

**作成日**: 2026-04-22  
**バージョン**: v1.0  
**対応フェーズ**: デザインシステム実装準備  

---

## 概要

本ガイドラインは、THEBRANCHプラットフォームで使用するフォント、サイズ、ウェイト、行高などの詳細仕様を定義します。一貫性のある読みやすいテキスト表現を実現します。

---

## 1. フォント選択

### 1.1 日本語フォント

**推奨フォント**: Noto Sans JP（Google Fonts）

```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;600;700&display=swap');

.jp-text {
  font-family: 'Noto Sans JP', sans-serif;
}
```

**特性**:
- 日本語のすべての文字セット（ひらがな、カタカナ、漢字、記号）に対応
- クリアで読みやすい設計
- ウェイト: 400（Regular）、600（SemiBold）、700（Bold）

### 1.2 英語 / 多言語フォント

**推奨フォント**: Inter（Google Fonts）+ システムフォント

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

body {
  font-family: 
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    'Helvetica Neue',
    'Inter',
    sans-serif;
}
```

**特性**:
- モダンで中立的なサンセリフ
- スクリーンでの可読性が優秀
- ウェイト: 400、500、600、700

**フォールバック順序**:
1. Inter（オンラインフォント）
2. -apple-system（macOS / iOS ネイティブ）
3. BlinkMacSystemFont（Chrome）
4. Segoe UI（Windows）
5. Helvetica Neue（レガシー）

### 1.3 コード表示用フォント

**推奨フォント**: Fira Code / Monaco

```css
.code, code, pre {
  font-family: 'Fira Code', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
}
```

---

## 2. タイポグラフィスケール

### 2.1 ヘッディング群

#### Heading 1（H1）- ページタイトル

```css
h1 {
  font-size: 32px;
  font-weight: 700; /* Bold */
  line-height: 1.2; /* 38.4px */
  letter-spacing: -0.5px;
  color: #111827; /* gray-900 */
  margin: 0 0 16px 0;
}
```

**使用例**: ダッシュボードのメインタイトル、ページヘッダー

**HTML**:
```html
<h1>AIエージェント部署管理</h1>
```

---

#### Heading 2（H2）- セクションタイトル

```css
h2 {
  font-size: 24px;
  font-weight: 700; /* Bold */
  line-height: 1.33; /* 32px */
  letter-spacing: -0.25px;
  color: #111827; /* gray-900 */
  margin: 0 0 12px 0;
}
```

**使用例**: セクション見出し、モーダルタイトル

**HTML**:
```html
<h2>タスク一覧</h2>
```

---

#### Heading 3（H3）- 小見出し

```css
h3 {
  font-size: 18px;
  font-weight: 600; /* SemiBold */
  line-height: 1.33; /* 24px */
  letter-spacing: 0px;
  color: #111827; /* gray-900 */
  margin: 0 0 8px 0;
}
```

**使用例**: カード内の小見出し、リスト項目グループ

**HTML**:
```html
<h3>実行中のタスク</h3>
```

---

#### Heading 4（H4）- サブ見出し（オプション）

```css
h4 {
  font-size: 16px;
  font-weight: 600; /* SemiBold */
  line-height: 1.5; /* 24px */
  letter-spacing: 0px;
  color: #1f2328; /* gray-900 */
  margin: 0 0 8px 0;
}
```

**使用例**: テーブルセクション、ダイアログのサブタイトル

---

### 2.2 ボディテキスト

#### Body（16px）- 標準テキスト

```css
p, .body-lg {
  font-size: 16px;
  font-weight: 400; /* Regular */
  line-height: 1.5; /* 24px */
  letter-spacing: 0px;
  color: #374151; /* gray-700 */
  margin: 0 0 16px 0;
}
```

**使用例**: ページ本文、説明テキスト、記事

**HTML**:
```html
<p>このダッシュボードでは、すべてのAIエージェント部署を管理できます。</p>
```

---

#### Body（14px）- 補助テキスト

```css
small, .body-sm {
  font-size: 14px;
  font-weight: 400; /* Regular */
  line-height: 1.5; /* 21px */
  letter-spacing: 0px;
  color: #4b5563; /* gray-600 */
  margin: 0 0 12px 0;
}
```

**使用例**: UIラベル、ヘルパーテキスト、フォーム説明

**HTML**:
```html
<small>最大 100 タスクまで登録可能です</small>
```

---

### 2.3 キャプション / ヘルパーテキスト

```css
caption, .caption {
  font-size: 12px;
  font-weight: 400; /* Regular */
  line-height: 1.33; /* 16px */
  letter-spacing: 0px;
  color: #6b7280; /* gray-500 */
  margin: 0 0 8px 0;
}
```

**使用例**: メタデータ、日付表示、メモ

**HTML**:
```html
<caption>更新日: 2026-04-22 10:30</caption>
```

---

### 2.4 コード表示

```css
code, pre {
  font-family: 'Fira Code', 'Monaco', monospace;
  font-size: 13px;
  font-weight: 400; /* Regular */
  line-height: 1.6; /* 21px */
  letter-spacing: 0px;
  color: #374151; /* gray-700 */
  background-color: #f3f4f6; /* gray-100 */
  padding: 2px 4px;
  border-radius: 2px;
}
```

**使用例**: APIレスポンス、エラーメッセージ、コード例

**HTML**:
```html
<code>GET /api/tasks/123</code>
```

---

## 3. スケール一覧表

### 3.1 クイックリファレンス

| 用途 | サイズ | ウェイト | 行高 | 色 | 例 |
|---|---|---|---|---|---|
| **H1** | 32px | 700 | 1.2 | gray-900 | ページタイトル |
| **H2** | 24px | 700 | 1.33 | gray-900 | セクション見出し |
| **H3** | 18px | 600 | 1.33 | gray-900 | カード見出し |
| **H4** | 16px | 600 | 1.5 | gray-900 | サブ見出し |
| **Body (16px)** | 16px | 400 | 1.5 | gray-700 | 本文 |
| **Body (14px)** | 14px | 400 | 1.5 | gray-600 | UIラベル |
| **Caption** | 12px | 400 | 1.33 | gray-500 | メタデータ |
| **Code** | 13px | 400 | 1.6 | gray-700 | コード |

---

## 4. 行高（Line Height）の理由

### 4.1 詳細説明

```
行高 = 行間スペース / フォントサイズ

例）
H1: line-height: 1.2
    = 32px × 1.2 = 38.4px（行間スペース）
    
Body: line-height: 1.5
    = 16px × 1.5 = 24px（行間スペース）
    = 読みやすさとコンパクトさのバランス
```

### 4.2 アクセシビリティ考慮

- **最小行高**: 1.4 （短いテキスト）
- **標準行高**: 1.5 （本文） ← ディスレクシア対応
- **広いテキスト**: 1.6+ （長文記事）

---

## 5. 実装例

### 5.1 HTML + CSS

```html
<style>
  h1 { font-size: 32px; font-weight: 700; line-height: 1.2; color: #111827; }
  h2 { font-size: 24px; font-weight: 700; line-height: 1.33; color: #111827; }
  p { font-size: 16px; font-weight: 400; line-height: 1.5; color: #374151; }
  small { font-size: 14px; font-weight: 400; line-height: 1.5; color: #4b5563; }
</style>

<h1>ダッシュボード</h1>
<p>AIエージェント部署の状態をリアルタイムで監視します。</p>
<small>最終更新: 2026-04-22</small>
```

### 5.2 TailwindCSS 実装

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      fontSize: {
        h1: ['32px', { lineHeight: '1.2', fontWeight: '700' }],
        h2: ['24px', { lineHeight: '1.33', fontWeight: '700' }],
        h3: ['18px', { lineHeight: '1.33', fontWeight: '600' }],
        body: ['16px', { lineHeight: '1.5', fontWeight: '400' }],
        sm: ['14px', { lineHeight: '1.5', fontWeight: '400' }],
        xs: ['12px', { lineHeight: '1.33', fontWeight: '400' }],
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Inter', 'sans-serif'],
        mono: ['Fira Code', 'Monaco', 'monospace'],
      },
    },
  },
};
```

**使用方法**:
```html
<h1 class="text-h1">タイトル</h1>
<p class="text-body">本文</p>
<small class="text-xs">キャプション</small>
```

---

## 6. 国際化対応（多言語）

### 6.1 日本語フォント設定

```css
:lang(ja) {
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 14px; /* 日本語はやや小さめ */
  letter-spacing: 0px;
}
```

### 6.2 英語フォント設定

```css
:lang(en) {
  font-family: 'Inter', sans-serif;
  font-size: 15px; /* 英語はやや大きめ */
  letter-spacing: 0.3px;
}
```

---

## 7. ダーク / ライトモード対応

### ライトモード（デフォルト）

```css
:root {
  --text-primary: #111827; /* gray-900 */
  --text-secondary: #374151; /* gray-700 */
  --text-muted: #6b7280; /* gray-500 */
}

p { color: var(--text-secondary); }
```

### ダークモード

```css
:root[data-theme="dark"] {
  --text-primary: #f3f4f6; /* gray-100 */
  --text-secondary: #d1d5db; /* gray-300 */
  --text-muted: #9ca3af; /* gray-400 */
}
```

---

## 8. アクセシビリティチェックリスト

- [ ] 最小フォントサイズ: 12px（キャプションのみ）
- [ ] 最小行高: 1.4（本文は 1.5 以上）
- [ ] コントラスト比: WCAG AA 基準（4.5:1 以上）
- [ ] レターバンプ：0 以上（負のマージン禁止）
- [ ] テキスト拡大: 200% で読可能性を確認
- [ ] スクリーンリーダー: セマンティック HTML（h1～h6）使用

---

## 9. 共通パターン

### 9.1 フォームラベル

```css
label {
  font-size: 14px;
  font-weight: 600; /* SemiBold */
  color: #1f2328; /* gray-800 */
  display: block;
  margin-bottom: 4px;
}
```

### 9.2 テーブルヘッダー

```css
th {
  font-size: 12px;
  font-weight: 600; /* SemiBold */
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #4b5563; /* gray-600 */
}
```

### 9.3 ボタンテキスト

```css
button {
  font-size: 14px;
  font-weight: 600; /* SemiBold */
  text-transform: none; /* または capitalize */
  letter-spacing: 0.2px;
}
```

---

## 10. チェックリスト（実装確認用）

- [ ] Noto Sans JP と Inter を Google Fonts から読み込み
- [ ] H1～H4 スケールを CSS クラスで定義
- [ ] Body、Small、Caption スケールを確認
- [ ] ダーク/ライト モード対応の色変数を設定
- [ ] すべてのテキスト色がコントラスト比 4.5:1 以上
- [ ] モバイル表示で行高が正しく適用されていることを確認

---

## 11. 参考リンク

- デザインシステム本体: `/docs/design/DESIGN_SYSTEM.md`
- カラーパレット仕様書: `/docs/design/COLOR_PALETTE_SPEC.md`
- Figma コンポーネント: 準備中
