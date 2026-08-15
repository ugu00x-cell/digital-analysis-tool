"""
駅名の表記統一を行うユーティリティ関数群（副作用なし）
"""


def normalize_station_name(raw_name: str) -> str:
    """駅名の表記を統一する（前後の空白除去・「駅」サフィックス付与）

    Args:
        raw_name: customer_dataから取得した生の駅名（例：「東京」「渋谷駅」）

    Returns:
        正規化された駅名（例：「東京駅」）。空文字・空白のみの場合は空文字を返す
    """
    if not raw_name:
        return ""

    name = raw_name.strip()
    if not name:
        return ""

    # 既に「駅」で終わっていなければ付与する
    if not name.endswith("駅"):
        name = f"{name}駅"

    return name


def build_directions_query(station_name: str, prefecture: str = "") -> str:
    """Directions APIに渡すクエリ文字列を組み立てる（都道府県名で曖昧さを軽減）

    Args:
        station_name: 正規化済みの駅名
        prefecture: 曖昧さ回避用の都道府県名（省略可）

    Returns:
        Directions APIのorigin/destinationパラメータに渡す文字列
    """
    if prefecture:
        return f"{prefecture}{station_name}"
    return station_name
