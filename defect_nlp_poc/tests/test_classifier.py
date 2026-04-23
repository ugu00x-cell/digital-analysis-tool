"""classifier.py のテスト。

API呼び出しはモックしてロジックのみ検証する。
正常系2・異常系2・境界値1の最低構成を満たす。
"""
from unittest.mock import MagicMock

import pytest

from classifier import (
    build_system_prompt,
    build_user_message,
    classify_batch,
    extract_json,
    merge_predictions,
)


# 正常系1: JSON抽出が成功する
def test_extract_json_success():
    text = 'ここが応答: {"results": [{"id": 1, "predicted_label": "bearing_noise"}]} 以上'
    parsed = extract_json(text)
    assert parsed is not None
    assert parsed["results"][0]["id"] == 1


# 正常系2: システムプロンプトに分類体系が全て含まれる
def test_system_prompt_contains_all_labels():
    prompt = build_system_prompt()
    for label in [
        "bearing_noise", "thermal_displacement", "assembly_scratch",
        "alignment_error", "dimension_oversize", "dimension_undersize",
        "surface_rust", "motion_alarm",
    ]:
        assert label in prompt


# 異常系1: 不正JSONはNone
def test_extract_json_invalid_returns_none():
    assert extract_json("これは普通のテキスト、JSONなし") is None
    # 壊れたJSON
    assert extract_json('{"results": [invalid}') is None


# 異常系2: 未知ラベルは空文字にフォールバックされる
def test_merge_predictions_rejects_unknown_label():
    rows = [{"id": "1", "date": "2024-01-01", "product_category": "マシニングセンタ",
             "defect_description": "異音", "true_label": "bearing_noise"}]
    predictions = [{"id": 1, "predicted_label": "存在しないラベル", "confidence": "high",
                    "sub_category": "", "estimated_cause": "", "countermeasure": ""}]
    merged = merge_predictions(rows, predictions)
    assert merged[0]["predicted_label"] == ""


# 境界値: 予測が空リストでも全行が空文字で返る
def test_merge_predictions_empty_predictions():
    rows = [{"id": "1", "date": "2024-01-01", "product_category": "研削盤",
             "defect_description": "傷", "true_label": "assembly_scratch"}]
    merged = merge_predictions(rows, [])
    assert len(merged) == 1
    assert merged[0]["predicted_label"] == ""
    assert merged[0]["confidence"] == ""


# 追加: classify_batchのAPIエラー時スキップ挙動
def test_classify_batch_api_error_returns_empty():
    from anthropic import APIError
    client = MagicMock()
    # APIErrorは request と body を要求するため、適当なダミーで raise
    client.messages.create.side_effect = APIError(
        message="boom", request=MagicMock(), body=None,
    )
    batch = [{"id": "1", "defect_description": "異音"}]
    result = classify_batch(client, batch)
    assert result == []


# 追加: user_messageにidとdescriptionが入る
def test_build_user_message_includes_inputs():
    batch = [{"id": "5", "defect_description": "カラカラ音"}]
    msg = build_user_message(batch)
    assert "カラカラ音" in msg
    assert '"id": 5' in msg or '"id":5' in msg
