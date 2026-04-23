# features/onboarding_flow.feature
Feature: オンボーディングフロー - 初回ユーザーが部署を作成する
  初回ユーザーとして
  オンボーディングウィザードを完了して
  自分の部署を立ち上げたい

  Scenario: ビジョン入力から部署作成まで
    Given ユーザーがログインしている
    When ユーザーが「営業チームを立ち上げて月商1000万円を達成したい」というビジョンを入力する
    Then AI分析によるテンプレート提案を受け取る
    And 提案に「営業推進部」が含まれている

    When ユーザーが「営業推進部」テンプレートを選択する
    And メンバー数を「3」に設定する
    And 予算を「16500」(USD/月)に設定する
    Then 詳細設定が保存される
    And 予算検証が「OK」となる

    When ユーザーが「実行」ボタンをクリックする
    Then 初期タスクが3-5個自動生成される
    And エージェントが起動状態になる
    And ダッシュボードにリダイレクトされる

  Scenario: ビジョン入力バリデーション
    Given ユーザーがログインしている
    When ユーザーが空のビジョンを入力しようとする
    Then エラーメッセージ「Vision input must be 10-500 characters」が表示される

    When ユーザーが500文字を超えるビジョンを入力しようとする
    Then エラーメッセージ「Vision input must be 10-500 characters」が表示される

  Scenario: 予算チェック警告
    Given ユーザーがStep 2（詳細設定）に進んでいる
    When ユーザーがメンバー数「3」で予算「9000」(USD/月)を設定する
    Then 予算検証が「warning」となる
    And 警告メッセージが表示される
    And ユーザーは続行できる

  Scenario: 複数のテンプレート提案から選択
    Given ユーザーがビジョン「カスタマーサクセスを最優先にしたい」を入力している
    When AI分析が実行される
    Then 複数のテンプレート提案（最大3個）が返される
    And 各提案は以下の情報を含む:
      | フィールド | 説明 |
      | template_id | テンプレートID |
      | name | テンプレート名 |
      | category | カテゴリ |
      | total_roles | 役割数 |
      | total_processes | プロセス数 |
      | reason | 選択理由 |
      | rank | マッチランク |
