# THEBRANCH Figma デザインシステムセットアップガイド

**作成日**: 2026-04-22  
**バージョン**: v1.0  
**対象**: UI/UXデザイナー  

---

## 概要

本ガイドは、Figmaでのデザインシステム構築手順を段階的に説明します。カラーライブラリ、タイポグラフィ、コンポーネントの統合的なセットアップを実施します。

---

## 1. 準備フェーズ

### 1.1 Figmaアカウント・ファイル作成

**前提条件**:
- Figmaアカウント（Professional以上推奨）
- チームワークスペースへのアクセス権

**セットアップ手順**:

1. **ファイル作成**
   ```
   Figma > New file > "THEBRANCH Design System v1.0"
   ```

2. **チームへ移動**
   ```
   Dashboard > Teams > [THEBRANCH チーム] > New file
   ```

3. **ファイル構成**
   ```
   THEBRANCH Design System
   ├── 📄 01_Colors
   ├── 📄 02_Typography
   ├── 📄 03_Components
   ├── 📄 04_Icons
   └── 📄 05_Patterns
   ```

---

## 2. カラーシステム構築（01_Colors）

### 2.1 プライマリカラーライブラリ作成

**Step 1: Color Styles を作成**

1. Figma メニュー > Assets > Colors
2. ウィンドウ左側の "+" をクリック
3. 新規カラースタイル作成

**Step 2: プライマリスケール定義**

| 名前 | 色値 | 操作 |
|---|---|---|
| `Primary/50` | `#EFF6FF` | 新規作成 |
| `Primary/100` | `#DBEAFE` | 新規作成 |
| `Primary/200` | `#BFDBFE` | 新規作成 |
| `Primary/300` | `#93C5FD` | 新規作成 |
| `Primary/400` | `#60A5FA` | 新規作成 |
| `Primary/500` | `#3B82F6` | 新規作成（メイン） |
| `Primary/600` | `#2563EB` | 新規作成 |
| `Primary/700` | `#1D4ED8` | 新規作成 |
| `Primary/800` | `#1E40AF` | 新規作成 |
| `Primary/900` | `#1E3A8A` | 新規作成 |

**実装例**:

```figma
1. Assets パネル右上の "..." > "New color style"
2. 色値を入力 (#3B82F6)
3. 名前を設定 (Primary/500)
4. "Create style" をクリック
```

---

### 2.2 セマンティックカラー定義

**Success / Warning / Error / Info**

```
Success
├── Success/50    #F0FDF4
├── Success/500   #22C55E
└── Success/700   #15803D

Warning
├── Warning/50    #FFFBEB
├── Warning/500   #FBBF24
└── Warning/700   #B45309

Error
├── Error/50      #FEF2F2
├── Error/500     #EF4444
└── Error/700     #B91C1C

Info
├── Info/50       #EFF6FF
├── Info/500      #3B82F6
└── Info/700      #1D4ED8
```

**Figma での作成方法**:

```
1. 各セマンティックカラーに対して "Group" を作成
   (例: Success グループ)
2. グループ内に色スケールを作成
3. ネスト構造: "Semantic/Success/500"
```

---

### 2.3 グレースケール（Gray）

```
Gray/50    #FAFAFA   (background)
Gray/100   #F3F4F6   (light bg)
Gray/200   #E5E7EB   (border)
Gray/300   #D1D5DB   (border dark)
Gray/400   #9CA3AF   (secondary text)
Gray/500   #6B7280   (secondary text)
Gray/600   #4B5563   (body text)
Gray/700   #374151   (body text dark)
Gray/800   #1F2937   (strong text)
Gray/900   #111827   (highest contrast)
```

---

### 2.4 ステータスカラー定義

```
Status/Priority/High      #EF4444  (P1)
Status/Priority/Medium    #FBBF24  (P2)
Status/Priority/Low       #6B7280  (P3)

Status/Task/Pending       #6B7280
Status/Task/InProgress    #3B82F6
Status/Task/Blocked       #F97316
Status/Task/Done          #22C55E
Status/Task/Failed        #EF4444

Status/Agent/Active       #22C55E  (🟢)
Status/Agent/Idle         #FBBF24  (🟡)
Status/Agent/Archived     #EF4444  (🔴)
```

---

## 3. タイポグラフィシステム構築（02_Typography）

### 3.1 フォント登録

**Step 1: フォントを追加**

1. Design tab > Fonts パネル
2. "+" をクリック
3. 以下を追加:
   - `Inter` (Google Fonts)
   - `Noto Sans JP` (Google Fonts)
   - `Fira Code` (monospace)

**Step 2: 確認**

```
✓ Inter    (Weights: 400, 500, 600, 700)
✓ Noto Sans JP (Weights: 400, 600, 700)
✓ Fira Code (monospace)
```

---

### 3.2 Typography Styles 作成

**Step 1: H1 スタイル作成**

```
名前:        Typography/H1
フォント:    Inter
サイズ:      32px
ウェイト:    700 (Bold)
行高:        1.2 (38.4px)
文字間:      -0.5px
色:          #111827 (gray-900)
```

**手順**:
1. テキストレイヤーを作成
2. 上記の設定を適用
3. Style > "+" でスタイル化

**Step 2: 残りのスタイル作成**

| スタイル名 | サイズ | ウェイト | 行高 | 色 |
|---|---|---|---|---|
| H2 | 24px | 700 | 1.33 | gray-900 |
| H3 | 18px | 600 | 1.33 | gray-900 |
| H4 | 16px | 600 | 1.5 | gray-900 |
| Body/Lg | 16px | 400 | 1.5 | gray-700 |
| Body/Sm | 14px | 400 | 1.5 | gray-600 |
| Caption | 12px | 400 | 1.33 | gray-500 |
| Code | 13px | 400 | 1.6 | gray-700 |

---

### 3.3 フォントサイズ定義（Grid）

**Figma で Responsive Sizing 設定**:

```
Create base frame:
- Desktop: 1280px width
- Tablet: 960px width
- Mobile: 375px width

Apply typography auto-sizing:
- Scale: 1.2x (Major Third)
```

---

## 4. コンポーネント構築（03_Components）

### 4.1 基本コンポーネント一覧

```
Components
├── Button
│   ├── Button/Primary
│   ├── Button/Secondary
│   ├── Button/Tertiary
│   └── Button/Danger
├── Input
│   ├── Input/Text
│   ├── Input/Search
│   └── Input/TextArea
├── Card
│   ├── Card/Elevated
│   ├── Card/Outlined
│   └── Card/Flat
├── Badge
│   ├── Badge/Default
│   ├── Badge/Primary
│   └── Badge/Status
├── Tag
│   ├── Tag/Filled
│   ├── Tag/Outlined
│   └── Tag/Tonal
└── Icon
    ├── Icon/16
    ├── Icon/20
    ├── Icon/24
    └── Icon/32
```

---

### 4.2 Button コンポーネント設計

**Step 1: フレーム作成**

```
1. Frame 作成: "Button/Primary"
2. サイズ: 160px × 40px (md)
3. 背景色: Primary/500 (#3B82F6)
4. 角丸: 4px
5. シャドウ: shadow-sm
```

**Step 2: バリアント定義**

```
Button/Primary
├── State: Default
│   └── bg: #3B82F6, text: white
├── State: Hover
│   └── bg: #2563EB, shadow: shadow-md
├── State: Active
│   └── bg: #1D4ED8
└── State: Disabled
    └── bg: #E5E7EB, opacity: 0.5
```

**Figma での実装**:
1. バリアントプロパティ作成: "State"
2. 値: Default / Hover / Active / Disabled
3. 各バリアントの見た目を編集
4. "Main component" に設定

---

### 4.3 Card コンポーネント設計

```
Card
├── Variant: Elevated
│   └── Shadow: shadow-sm, Border: none
├── Variant: Outlined
│   └── Border: 1px gray-200, Shadow: none
└── Variant: Flat
    └── bg: gray-50, Border: none
```

**構造**:
```
Card (Main)
├── CardHeader (text + actions)
├── CardContent (main content)
└── CardFooter (buttons/metadata)
```

---

## 5. アイコンシステム構築（04_Icons）

### 5.1 アイコン整理

**推奨**: Material Icons / Feather Icons の活用

```
Icons
├── Functional
│   ├── icon/task
│   ├── icon/dashboard
│   ├── icon/settings
│   ├── icon/notification
│   ├── icon/search
│   └── icon/menu
├── Status
│   ├── icon/success (✓)
│   ├── icon/warning (⚠️)
│   ├── icon/error (❌)
│   └── icon/loading (⏳)
└── Semantic
    ├── icon/arrow-up
    ├── icon/arrow-down
    └── icon/expand
```

### 5.2 アイコンスタイル定義

```
Size: 16px, 20px, 24px, 32px
Weight: 1.5px (stroke)
Color: gray-600 (default)
Variants: 4 sizes × 3 colors (primary, success, error)
```

---

## 6. パターン & テンプレート（05_Patterns）

### 6.1 よく使うパターン集

```
Patterns
├── Form
│   ├── LoginForm
│   ├── TaskForm
│   └── FilterForm
├── Layout
│   ├── Header
│   ├── Sidebar
│   ├── MainContent
│   └── Footer
├── Cards
│   ├── TaskCard
│   ├── AgentCard
│   └── DepartmentCard
└── Modal
    ├── ConfirmDialog
    ├── AlertDialog
    └── FormModal
```

---

## 7. Design System ドキュメント作成

### 7.1 Figma Wireframe での説明書

**Page 作成**: `📖 Guidelines`

```
- カラーパレット表 (表示 + HEX値)
- タイポグラフィスケール表 (表示 + 実装値)
- コンポーネント使用例
- アクセシビリティ注記
- 実装チェックリスト
```

---

## 8. チーム共有設定

### 8.1 Figma Sharing

```
1. Share > Anyone with link
2. Can view ← デザインチーム用
3. Can edit ← 自分とリーダー用
```

### 8.2 Dev Hand-off

```
Figma > Inspect > CSS コード生成
→ フロントエンドチームへ引き渡し
```

---

## 9. 今後の拡張計画

### Phase 2: ダークモード

```
Color Styles
├── Color Mode: Light
└── Color Mode: Dark
    ├── Primary/500: #3B82F6 → #60A5FA
    ├── Gray/900: #111827 → #FAFAFA
    └── ... (全色対応)
```

### Phase 3: レスポンシブ対応

```
Breakpoints:
- Mobile: < 640px
- Tablet: 640-1024px
- Desktop: > 1024px
```

---

## 10. チェックリスト（セットアップ完了確認）

- [ ] **カラー**: Primary, Semantic, Gray, Status のスタイル全て作成
- [ ] **タイポグラフィ**: H1-H4, Body, Caption, Code スタイル作成
- [ ] **コンポーネント**: Button, Input, Card, Badge, Tag 実装
- [ ] **アイコン**: 基本 20+ 個のアイコン登録
- [ ] **パターン**: Form, Layout, Card, Modal テンプレート作成
- [ ] **ドキュメント**: ガイドラインページ作成・説明追加
- [ ] **共有**: チームメンバーに閲覧権限を付与
- [ ] **Design Tokens**: CSS 変数リスト作成
- [ ] **コントラスト**: 全色の WCAG AA 対応確認
- [ ] **アクセシビリティ**: スクリーンリーダー配慮の注記追加

---

## 11. トラブルシューティング

### よくある問題

#### Q1: Figma でフォントが反映されない

**解決方法**:
```
1. Figma > Preferences > General
2. "Reload assets" をクリック
3. または、Google Fonts から再度フォント追加
```

#### Q2: スタイルの更新が反映されない

**解決方法**:
```
1. Main Component を確認
2. Edit style > Update
3. すべてのインスタンスに適用されることを確認
```

#### Q3: 色が印刷やエクスポート時に変わる

**解決方法**:
```
1. カラープロファイル: sRGB 使用
2. Export 時の色空間: RGB 選択
3. 事前にプレビューで確認
```

---

## 12. 参考リンク・リソース

- **Figma サポート**: https://help.figma.com/
- **Design System Guide**: https://www.designsystems.com/
- **Material Design**: https://m3.material.io/
- **THEBRANCH Design System 本体**: `/docs/design/DESIGN_SYSTEM.md`
- **カラーパレット仕様**: `/docs/design/COLOR_PALETTE_SPEC.md`
- **タイポグラフィガイド**: `/docs/design/TYPOGRAPHY_GUIDELINE.md`

---

## 次ステップ

✅ セットアップ完了後:
1. UIコンポーネント詳細設計（persona_design フェーズ）
2. ワイヤーフレーム & ハイフィデリティプロトタイプ作成
3. ユーザーテスト準備
4. 開発チームへの引き渡し
