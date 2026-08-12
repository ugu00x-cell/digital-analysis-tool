"""テキスト マッチング・表記ゆれ補正"""

import logging
from typing import Optional, Tuple, List
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class TextMatcher:
    """
    駅名・沿線名などのテキストマッチングと表記ゆれ補正を行うクラス
    """

    # よくある表記ゆれパターン
    COMMON_PATTERNS = {
        "JR": "JR|ＪＲ",
        "駅": "駅|站",
        "線": "線|線",
        "・": "・|・",
    }

    def __init__(self, threshold: float = 0.8):
        """
        初期化

        Args:
            threshold: マッチと判定する類似度の閾値（0.0-1.0）
        """
        self.threshold = threshold
        logger.info(f"TextMatcher initialized with threshold={threshold}")

    def normalize_text(self, text: str) -> str:
        """
        テキストを正規化（表記ゆれを統一）

        Args:
            text: 入力テキスト

        Returns:
            正規化されたテキスト
        """
        if not text:
            return ""

        result = str(text).strip()

        # 全角英数字を半角に統一
        result = result.translate(
            str.maketrans(
                "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ０１２３４５６７８９",
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            )
        )

        # 余分なスペースを削除
        result = " ".join(result.split())

        logger.debug(f"Normalized: {text} -> {result}")
        return result

    def similarity(self, text1: str, text2: str) -> float:
        """
        2つのテキストの類似度を計算（0.0-1.0）

        Args:
            text1: テキスト1
            text2: テキスト2

        Returns:
            類似度（0.0-1.0）
        """
        n1 = self.normalize_text(text1)
        n2 = self.normalize_text(text2)

        # SequenceMatcher で類似度計算
        ratio = SequenceMatcher(None, n1, n2).ratio()
        logger.debug(f"Similarity: '{n1}' vs '{n2}' = {ratio:.2f}")
        return ratio

    def find_best_match(
        self, query: str, candidates: List[str]
    ) -> Optional[Tuple[str, float]]:
        """
        クエリに最も一致する候補を検索

        Args:
            query: 検索クエリ（駅名・沿線名等）
            candidates: 候補テキストのリスト

        Returns:
            (最高一致テキスト, 類似度) のタプル。
            閾値以上の一致が見つからない場合は None
        """
        best_match = None
        best_score = 0.0

        for candidate in candidates:
            score = self.similarity(query, candidate)
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_score >= self.threshold:
            logger.info(
                f"Found best match for '{query}': '{best_match}' (score={best_score:.2f})"
            )
            return (best_match, best_score)
        else:
            logger.debug(f"No match found for '{query}' (best score={best_score:.2f})")
            return None

    def correct_station_name(self, station_name: str) -> str:
        """
        駅名を補正（例："中央線" -> "JR中央線"）

        Args:
            station_name: 駅名

        Returns:
            補正後の駅名
        """
        if not station_name:
            return ""

        normalized = self.normalize_text(station_name)

        # 「駅」サフィックスが無い場合は追加
        if not normalized.endswith("駅"):
            normalized = f"{normalized}駅"

        # JR・私鉄の区別がない場合、コンテキストから推測可能な場合は追加
        # （ここでは簡易実装）

        logger.debug(f"Corrected station name: '{station_name}' -> '{normalized}'")
        return normalized

    def correct_line_name(self, line_name: str) -> str:
        """
        沿線名を補正（例："中央線" -> "JR中央線"）

        Args:
            line_name: 沿線名

        Returns:
            補正後の沿線名
        """
        if not line_name:
            return ""

        normalized = self.normalize_text(line_name)

        # 「線」サフィックスが無い場合は追加
        if not normalized.endswith("線"):
            normalized = f"{normalized}線"

        logger.debug(f"Corrected line name: '{line_name}' -> '{normalized}'")
        return normalized

    def batch_match(
        self, query_list: List[str], master_list: List[str]
    ) -> dict:
        """
        複数のクエリを一括マッチング

        Args:
            query_list: クエリのリスト
            master_list: マスタリスト（対応関係を持つテーブルから）

        Returns:
            {クエリ: (マッチ結果, 類似度)} の辞書
        """
        results = {}
        for query in query_list:
            match = self.find_best_match(query, master_list)
            results[query] = match

        logger.info(f"Batch match completed: {len(results)} queries")
        return results
