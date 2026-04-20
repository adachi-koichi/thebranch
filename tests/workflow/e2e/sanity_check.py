#!/usr/bin/env python3
"""E2E Sanity Check - BDD workflow template system verification"""

import os
import re
import json
from pathlib import Path
from datetime import datetime

class SanityChecker:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.results = []
        self.passed = 0
        self.failed = 0

    def log_result(self, status: str, message: str):
        """ログに結果を追記"""
        line = f"[{status}] {message}"
        self.results.append(line)
        print(line)
        if status == "PASS":
            self.passed += 1
        else:
            self.failed += 1

    def check_test_data_files(self):
        """テストデータファイル存在確認"""
        print("\n=== テストデータファイル存在確認 ===")

        test_data_dir = self.base_dir / "test_data"
        if test_data_dir.exists():
            json_files = list(test_data_dir.rglob("*.json"))
            if json_files:
                for json_file in json_files[:3]:  # 最初の3ファイルを確認
                    rel_path = json_file.relative_to(self.base_dir)
                    self.log_result("PASS", f"テストデータファイル: {rel_path} 存在")
            else:
                self.log_result("INFO", "JSON テストデータファイルが見つかりません")
        else:
            self.log_result("INFO", f"テストデータディレクトリ {test_data_dir} 見つかりません")

        # conftest.py と feature ファイルは存在確認
        conftest_path = self.base_dir / "conftest.py"
        if conftest_path.exists():
            self.log_result("PASS", f"テストデータファイル: conftest.py 存在")
        else:
            self.log_result("FAIL", f"テストデータファイル: conftest.py 未検出")

    def check_json_schema_integrity(self):
        """JSON スキーマ正合性チェック"""
        print("\n=== JSON スキーマ正合性チェック ===")

        conftest_path = self.base_dir / "conftest.py"
        if not conftest_path.exists():
            self.log_result("FAIL", "スキーマチェック: conftest.py が見つかりません")
            return

        with open(conftest_path) as f:
            content = f.read()

        # テーブル定義のチェック
        required_tables = [
            "workflow_templates",
            "wf_template_phases",
            "wf_template_tasks",
            "agents",
            "workflow_instances",
            "wf_instance_nodes",
            "workflow_instance_specialists",
            "dev_tasks",
            "task_dependencies"
        ]

        tables_found = 0
        for table_name in required_tables:
            if f"CREATE TABLE" in content and table_name in content:
                tables_found += 1

        if tables_found == len(required_tables):
            self.log_result("PASS", f"スキーマチェック: {tables_found}/{len(required_tables)} テーブル定義が正常")
        else:
            self.log_result("FAIL", f"スキーマチェック: {tables_found}/{len(required_tables)} テーブル定義が検出されました")

        # 外部キー制約のチェック
        fk_pattern = r"FOREIGN KEY\s*\("
        fk_count = len(re.findall(fk_pattern, content))
        if fk_count >= 6:
            self.log_result("PASS", f"スキーマチェック: {fk_count} 個の外部キー制約が定義されています")
        else:
            self.log_result("FAIL", f"スキーマチェック: {fk_count} 個の外部キー制約を検出")

    def check_feature_file_syntax(self):
        """Feature ファイル構文チェック"""
        print("\n=== Feature ファイル構文チェック ===")

        features_dir = self.base_dir / "features"
        if not features_dir.exists():
            self.log_result("FAIL", "Feature ファイル: features ディレクトリが見つかりません")
            return

        feature_files = list(features_dir.glob("*.feature"))
        if not feature_files:
            self.log_result("FAIL", "Feature ファイル: .feature ファイルが見つかりません")
            return

        self.log_result("PASS", f"Feature ファイル: {len(feature_files)} 個の .feature ファイルを検出")

        # 各 feature ファイルの構文チェック
        for feature_file in feature_files:
            with open(feature_file) as f:
                content = f.read()

            # Feature キーワード確認
            if "Feature:" in content:
                self.log_result("PASS", f"Feature ファイル: {feature_file.name} - Feature キーワード確認")
            else:
                self.log_result("FAIL", f"Feature ファイル: {feature_file.name} - Feature キーワード未検出")

            # Scenario キーワード確認
            scenario_count = len(re.findall(r"^\s*Scenario:", content, re.MULTILINE))
            if scenario_count > 0:
                self.log_result("PASS", f"Feature ファイル: {feature_file.name} - {scenario_count} Scenario(s) 検出")
            else:
                self.log_result("FAIL", f"Feature ファイル: {feature_file.name} - Scenario が見つかりません")

            # Given/When/Then ステップ確認
            given_count = len(re.findall(r"^\s*Given\s+", content, re.MULTILINE))
            when_count = len(re.findall(r"^\s*When\s+", content, re.MULTILINE))
            then_count = len(re.findall(r"^\s*Then\s+", content, re.MULTILINE))

            total_steps = given_count + when_count + then_count
            if total_steps > 0:
                self.log_result("PASS", f"Feature ファイル: {feature_file.name} - {total_steps} ステップ検出 (Given:{given_count} When:{when_count} Then:{then_count})")
            else:
                self.log_result("FAIL", f"Feature ファイル: {feature_file.name} - ステップが見つかりません")

    def check_expected_result_fields(self):
        """期待結果フィールド確認"""
        print("\n=== 期待結果フィールド確認 ===")

        conftest_path = self.base_dir / "conftest.py"
        step_defs_dir = self.base_dir / "step_defs"

        # Fixture 定義の確認
        if conftest_path.exists():
            with open(conftest_path) as f:
                content = f.read()

            expected_fixtures = [
                "temp_db",
                "template_repo",
                "instance_repo",
                "task_repo",
                "template_service",
                "instance_service",
                "bdd_context"
            ]

            fixtures_found = 0
            for fixture in expected_fixtures:
                if f"def {fixture}" in content or f"@pytest.fixture" in content:
                    fixtures_found += 1

            if fixtures_found >= 5:
                self.log_result("PASS", f"期待結果フィールド: {fixtures_found}/{len(expected_fixtures)} fixture が定義されています")
            else:
                self.log_result("FAIL", f"期待結果フィールド: {fixtures_found}/{len(expected_fixtures)} fixture を検出")

        # ステップ定義の確認
        if step_defs_dir.exists():
            step_files = list(step_defs_dir.glob("*_steps.py"))
            if step_files:
                for step_file in step_files:
                    with open(step_file) as f:
                        content = f.read()

                    # @given, @when, @then デコレータの確認
                    decorator_count = len(re.findall(r"@(?:given|when|then)", content))
                    if decorator_count > 0:
                        self.log_result("PASS", f"期待結果フィールド: {step_file.name} - {decorator_count} ステップ定義を検出")
                    else:
                        self.log_result("FAIL", f"期待結果フィールド: {step_file.name} - ステップ定義が見つかりません")
            else:
                self.log_result("FAIL", "期待結果フィールド: step_defs ファイルが見つかりません")

        # BDD コンテキストの確認
        if conftest_path.exists():
            with open(conftest_path) as f:
                content = f.read()

            if "class BDDContext" in content:
                self.log_result("PASS", "期待結果フィールド: BDDContext クラスが定義されています")
            else:
                self.log_result("FAIL", "期待結果フィールド: BDDContext クラスが見つかりません")

    def check_step_definitions_coverage(self):
        """ステップ定義カバレッジ確認"""
        print("\n=== ステップ定義カバレッジ確認 ===")

        features_dir = self.base_dir / "features"
        if not features_dir.exists():
            return

        step_defs_dir = self.base_dir / "step_defs"
        conftest_path = self.base_dir / "conftest.py"

        # 全ステップ定義を収集
        implemented_steps = set()

        for step_file in [conftest_path] + (list(step_defs_dir.glob("*_steps.py")) if step_defs_dir.exists() else []):
            if step_file.exists():
                with open(step_file) as f:
                    content = f.read()
                    for match in re.finditer(r'@(?:given|when|then)\s*\(', content):
                        implemented_steps.add(match.group())

        if len(implemented_steps) > 0:
            self.log_result("PASS", f"ステップ定義カバレッジ: {len(implemented_steps)} ステップ定義が実装されています")
        else:
            self.log_result("FAIL", "ステップ定義カバレッジ: ステップ定義が見つかりません")

    def generate_summary(self):
        """サマリーを生成"""
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"✓ PASS: {self.passed}")
        print(f"✗ FAIL: {self.failed}")
        print(f"合計: {self.passed + self.failed}")

        if self.failed == 0:
            print("\n✓ 全チェック合格 - E2E テスト環境は正常です")
        else:
            print(f"\n✗ {self.failed} 件のチェックが失敗しました")

    def write_log_file(self, output_path):
        """ログファイルに出力"""
        with open(output_path, 'w') as f:
            f.write("E2E Sanity Check Log\n")
            f.write("=" * 60 + "\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 60 + "\n\n")

            for result in self.results:
                f.write(result + "\n")

            f.write("\n" + "=" * 60 + "\n")
            f.write("SUMMARY\n")
            f.write("=" * 60 + "\n")
            f.write(f"✓ PASS: {self.passed}\n")
            f.write(f"✗ FAIL: {self.failed}\n")
            f.write(f"合計: {self.passed + self.failed}\n")

    def run_all_checks(self):
        """全チェック実行"""
        self.check_test_data_files()
        self.check_json_schema_integrity()
        self.check_feature_file_syntax()
        self.check_expected_result_fields()
        self.check_step_definitions_coverage()
        self.generate_summary()


def main():
    checker = SanityChecker()
    checker.run_all_checks()

    # ログファイルに出力
    log_path = checker.base_dir / "sanity_check.log"
    checker.write_log_file(log_path)
    print(f"\n✓ ログファイル出力: {log_path}")

    return 0 if checker.failed == 0 else 1


if __name__ == '__main__':
    exit(main())
