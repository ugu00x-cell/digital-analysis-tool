"""コスプレ評価モジュールのテスト

parse_evaluation のパースロジック＋日本語変換を中心にテスト。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "cosplay_evaluator"))

from services.ollama_client import (  # noqa: E402
    CategoryScore,
    EvalResult,
    _extract_advice,
    _extract_score,
    _to_japanese,
    _translate_advice,
    parse_evaluation,
)


# ========== 正常系テスト ==========

class TestParseEvaluation:
    """parse_evaluation の正常系テスト"""

    SAMPLE_RESPONSE = """Expression: 16/20 - Good eye contact and natural smile.
Costume: 18/20 - Highly detailed costume with accurate colors.
Pose: 14/20 - Static pose could use more dynamic movement.
Lighting: 12/20 - Flat lighting with minimal shadows.
Overall: 15/20 - Good representation but room for improvement.
Total: 75/100
Advice1: Try using side lighting to add depth.
Advice2: Add more dynamic poses that match the character.
Advice3: Simplify the background to make the subject stand out."""

    def test_parse_all_scores(self) -> None:
        """5項目すべてのスコアがパースできる"""
        result = parse_evaluation(self.SAMPLE_RESPONSE)
        assert len(result.scores) == 5

    def test_parse_total_score(self) -> None:
        """合計スコアが正しく計算される"""
        result = parse_evaluation(self.SAMPLE_RESPONSE)
        assert result.total == 16 + 18 + 14 + 12 + 15

    def test_reasons_are_japanese(self) -> None:
        """理由が日本語テンプレートで生成されている"""
        result = parse_evaluation(self.SAMPLE_RESPONSE)
        for s in result.scores:
            # 日本語のひらがな・カタカナが含まれている
            assert any('\u3040' <= c <= '\u30ff' for c in s.reason)

    def test_advice_is_japanese(self) -> None:
        """アドバイスが日本語に変換されている"""
        result = parse_evaluation(self.SAMPLE_RESPONSE)
        assert len(result.advice) == 3
        # lightingキーワード → 日本語変換
        assert "ライティング" in result.advice[0]

    def test_original_reason_appended(self) -> None:
        """英語の原文が補足として含まれている"""
        result = parse_evaluation(self.SAMPLE_RESPONSE)
        expr = result.scores[0]  # Expression: 16/20
        assert "Good eye contact" in expr.reason


# ========== 日本語変換テスト ==========

class TestToJapanese:
    """_to_japanese のテスト"""

    def test_high_score(self) -> None:
        """15点以上で高評価テンプレート"""
        ja = _to_japanese("Expression", 18, "Great expression.")
        assert "見事に再現" in ja
        assert "Great expression" in ja

    def test_mid_score(self) -> None:
        """8〜14点で中評価テンプレート"""
        ja = _to_japanese("Costume", 10, "Decent costume.")
        assert "改善" in ja or "フィット感" in ja

    def test_low_score(self) -> None:
        """7点以下で低評価テンプレート"""
        ja = _to_japanese("Pose", 5, "Stiff pose.")
        assert "単調" in ja or "意識" in ja


class TestTranslateAdvice:
    """_translate_advice のテスト"""

    def test_lighting_keyword(self) -> None:
        """lightingキーワードで日本語変換"""
        ja = _translate_advice("Try better lighting setup")
        assert "ライティング" in ja

    def test_background_keyword(self) -> None:
        """backgroundキーワードで日本語変換"""
        ja = _translate_advice("Simplify the background")
        assert "背景" in ja

    def test_no_match_returns_original(self) -> None:
        """マッチしない場合は原文を返す"""
        ja = _translate_advice("Something very unique")
        assert "Something very unique" in ja


# ========== 異常系テスト ==========

class TestEdgeCases:
    """異常系・境界値テスト"""

    def test_empty_text(self) -> None:
        """空テキストでもエラーにならない"""
        result = parse_evaluation("")
        assert result.total == 0
        assert len(result.scores) == 5

    def test_score_over_20_capped(self) -> None:
        """20点を超えるスコアは20に丸められる"""
        score, _ = _extract_score("Expression: 25/20 - Amazing", "Expression")
        assert score == 20

    def test_zero_score(self) -> None:
        """0点のパース"""
        score, _ = _extract_score("Expression: 0/20 - Bad", "Expression")
        assert score == 0
