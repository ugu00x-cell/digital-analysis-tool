"""チェック結果のデータクラス定義"""

from dataclasses import dataclass, field


@dataclass
class CheckItem:
    """個別チェック項目の結果

    Attributes:
        name: チェック項目名
        passed: 合格したかどうか
        details: 問題箇所の詳細説明
        locations: 問題が見つかった箇所（行番号や引用）
    """

    name: str
    passed: bool
    details: str = ""
    locations: list[str] = field(default_factory=list)


@dataclass
class CheckReport:
    """1回のチェック全体の結果

    Attributes:
        loop_number: 何回目のチェックか（1〜3）
        items: 各チェック項目の結果リスト
        all_passed: 全項目合格したか
        summary: チェック結果の要約テキスト
    """

    loop_number: int
    items: list[CheckItem] = field(default_factory=list)
    summary: str = ""

    @property
    def all_passed(self) -> bool:
        """全チェック項目が合格しているか判定する"""
        return all(item.passed for item in self.items)

    @property
    def passed_count(self) -> int:
        """合格した項目数を返す"""
        return sum(1 for item in self.items if item.passed)

    @property
    def failed_count(self) -> int:
        """不合格の項目数を返す"""
        return sum(1 for item in self.items if not item.passed)

    def to_log_text(self) -> str:
        """ログ出力用のテキストを生成する"""
        lines: list[str] = []
        lines.append(f"=== チェック {self.loop_number}回目 ===")
        lines.append(
            f"結果: {self.passed_count}/{len(self.items)} 合格"
        )
        lines.append("")

        for item in self.items:
            # 合否マーク
            mark = "✅" if item.passed else "❌"
            lines.append(f"{mark} {item.name}")
            if not item.passed and item.details:
                lines.append(f"   → {item.details}")
            # 問題箇所の引用
            for loc in item.locations:
                lines.append(f"   📍 {loc}")
            lines.append("")

        if self.summary:
            lines.append(f"要約: {self.summary}")
        return "\n".join(lines)
