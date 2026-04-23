"""製造業 初期不良分類POC用のカテゴリ定義と合成データ。

竹中さんが正解ラベルを品質管理の知識で修正できるように、
データは `correct_label` を書き換え可能なdataclassで保持する。
"""
from dataclasses import dataclass
from typing import Optional


# 分類カテゴリ（5カテゴリ固定）
CATEGORIES: list[str] = [
    "外観不良",
    "寸法・形状不良",
    "機能・動作不良",
    "組立不良",
    "材料・素材不良",
]

# カテゴリ定義（LLMへのプロンプトに埋め込むための説明文）
CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "外観不良": "表面の傷・汚れ・変色・バリなど、見た目の欠陥",
    "寸法・形状不良": "寸法公差外れ・歪み・反り・位置ずれなど、形状の欠陥",
    "機能・動作不良": "動作しない・異音・性能未達など、機能面の欠陥",
    "組立不良": "部品欠品・締結不良・誤組など、組立工程起因の欠陥",
    "材料・素材不良": "割れ・クラック・介在物・材質違いなど、素材起因の欠陥",
}


@dataclass
class DefectSample:
    """初期不良の1サンプル。

    Attributes:
        text: 不良内容の日本語記述（10〜30文字程度）
        correct_label: 正解カテゴリ。Noneの場合は正解率計算から除外する
                       （竹中さんが後から修正できる形）
    """
    text: str
    correct_label: Optional[str] = None


# 合成データ20件（5カテゴリ × 4件ずつ）
# 正解ラベルは暫定値。竹中さんが品質管理の知識で修正してください。
SAMPLES: list[DefectSample] = [
    # 外観不良
    DefectSample("表面に細かい傷が複数ある", "外観不良"),
    DefectSample("塗装にムラが見られる", "外観不良"),
    DefectSample("端部にバリが残っている", "外観不良"),
    DefectSample("側面に変色箇所がある", "外観不良"),

    # 寸法・形状不良
    DefectSample("外径寸法が公差外れ", "寸法・形状不良"),
    DefectSample("取付穴の位置がずれている", "寸法・形状不良"),
    DefectSample("板金が全体的に歪んでいる", "寸法・形状不良"),
    DefectSample("平面度が規格を満たさない", "寸法・形状不良"),

    # 機能・動作不良
    DefectSample("電源を入れても起動しない", "機能・動作不良"),
    DefectSample("運転中に異音が発生する", "機能・動作不良"),
    DefectSample("回転数が規格値に届かない", "機能・動作不良"),
    DefectSample("動作が途中で停止する", "機能・動作不良"),

    # 組立不良
    DefectSample("固定ネジが1本不足している", "組立不良"),
    DefectSample("内部のケーブルが外れている", "組立不良"),
    DefectSample("部品の向きが逆に組付けられている", "組立不良"),
    DefectSample("カバーのはめ込みが甘い", "組立不良"),

    # 材料・素材不良
    DefectSample("内部にクラックが確認された", "材料・素材不良"),
    DefectSample("鋳造品の表面に鋳巣が出ている", "材料・素材不良"),
    DefectSample("素材の硬度が証明書と異なる", "材料・素材不良"),
    DefectSample("素材内部に異物が混入している", "材料・素材不良"),
]
