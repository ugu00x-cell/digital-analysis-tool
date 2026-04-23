"""初期不良分類の分類体系（ラベル定義）。

分類体系は品質管理の知識で後から修正される前提のため、
このファイルを編集するだけで全スクリプトに反映される設計。
"""


# 細分化ラベル（英語キー＋日本語説明）
# キーを変更する場合は generate_synthetic_data.py のテンプレート辞書も要修正
LABELS: dict[str, str] = {
    "bearing_noise": "ベアリング起因の異音・振動",
    "thermal_displacement": "熱変位による寸法ずれ",
    "assembly_scratch": "組立時の打痕・傷",
    "alignment_error": "芯出し・取付不良",
    "dimension_oversize": "加工寸法オーバー",
    "dimension_undersize": "加工寸法アンダー",
    "surface_rust": "錆・表面処理不良",
    "motion_alarm": "動作異常・アラーム",
}


# 製品カテゴリ
PRODUCT_CATEGORIES: list[str] = [
    "マシニングセンタ",
    "放電加工機",
    "研削盤",
]


def label_keys() -> list[str]:
    """ラベルキーのリストを返す。"""
    return list(LABELS.keys())


def format_labels_for_prompt() -> str:
    """LLMプロンプト用に分類体系を整形して返す。

    Returns:
        "- bearing_noise: ベアリング起因の異音・振動" 形式の箇条書き文字列
    """
    return "\n".join(f"- {key}: {desc}" for key, desc in LABELS.items())
