"""CheckReport / CheckItem のユニットテスト"""

import pytest

from models.check_result import CheckItem, CheckReport


class TestCheckItem:
    """CheckItemデータクラスのテスト"""

    def test_create_passed_item(self) -> None:
        """正常系：合格アイテムの生成"""
        item = CheckItem(name="対比描写", passed=True)
        assert item.name == "対比描写"
        assert item.passed is True
        assert item.details == ""
        assert item.locations == []

    def test_create_failed_item_with_details(self) -> None:
        """正常系：不合格アイテムに詳細と箇所が設定される"""
        item = CheckItem(
            name="五感描写",
            passed=False,
            details="視覚のみ。聴覚・触覚が不足",
            locations=["3行目: 彼女は青い服を着ていた"],
        )
        assert item.passed is False
        assert "視覚のみ" in item.details
        assert len(item.locations) == 1


class TestCheckReport:
    """CheckReportデータクラスのテスト"""

    def _make_report(
        self, passed_flags: list[bool]
    ) -> CheckReport:
        """テスト用レポートを生成するヘルパー"""
        report = CheckReport(loop_number=1)
        for i, passed in enumerate(passed_flags):
            report.items.append(
                CheckItem(
                    name=f"項目{i+1}",
                    passed=passed,
                    details="" if passed else f"問題{i+1}",
                )
            )
        return report

    def test_all_passed_true(self) -> None:
        """正常系：全合格でall_passedがTrue"""
        report = self._make_report([True, True, True])
        assert report.all_passed is True
        assert report.passed_count == 3
        assert report.failed_count == 0

    def test_all_passed_false(self) -> None:
        """正常系：1つでも不合格でall_passedがFalse"""
        report = self._make_report([True, False, True])
        assert report.all_passed is False
        assert report.passed_count == 2
        assert report.failed_count == 1

    def test_empty_report_all_passed(self) -> None:
        """境界値：項目なしでもall_passedはTrue（all()の仕様）"""
        report = CheckReport(loop_number=1)
        assert report.all_passed is True
        assert report.passed_count == 0

    def test_to_log_text_contains_marks(self) -> None:
        """正常系：ログテキストに合否マークが含まれる"""
        report = self._make_report([True, False])
        report.summary = "テスト要約"
        log = report.to_log_text()
        assert "✅" in log
        assert "❌" in log
        assert "テスト要約" in log
        assert "チェック 1回目" in log

    def test_to_log_text_shows_locations(self) -> None:
        """正常系：問題箇所がログテキストに表示される"""
        report = CheckReport(loop_number=2)
        report.items.append(
            CheckItem(
                name="視点のブレ",
                passed=False,
                details="途中で視点が切り替わっている",
                locations=["5行目: 部長は内心焦っていた"],
            )
        )
        log = report.to_log_text()
        assert "📍" in log
        assert "5行目" in log

    def test_all_failed(self) -> None:
        """異常系：全項目不合格"""
        report = self._make_report([False, False, False])
        assert report.all_passed is False
        assert report.failed_count == 3

    def test_single_item_failed(self) -> None:
        """異常系：1項目のみで不合格"""
        report = self._make_report([False])
        assert report.all_passed is False
        assert report.passed_count == 0
        assert report.failed_count == 1
