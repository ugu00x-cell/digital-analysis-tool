"""台本チェック＆修正ロジック

8つのチェック項目でスカッと動画の台本を評価し、
不合格項目があればClaude APIで修正を繰り返す。
"""

import logging

from models.check_result import CheckItem, CheckReport
from services.claude_client import call_claude, call_claude_json

logger = logging.getLogger(__name__)

# 最大修正ループ回数
MAX_LOOPS = 3

# チェック項目の定義（ID・名前・説明）
CHECK_ITEMS: list[dict[str, str]] = [
    {
        "id": "contrast",
        "name": "対比描写",
        "desc": "対比描写が同一文内に入っているか（例：貧しい主人公 vs 裕福な悪役）",
    },
    {
        "id": "senses",
        "name": "五感描写",
        "desc": "視覚・聴覚・触覚・嗅覚のうち2つ以上の五感描写があるか",
    },
    {
        "id": "viewpoint",
        "name": "視点のブレ",
        "desc": "視点人物が途中でブレていないか（主人公視点なのに急に別人の心情を描写していないか）",
    },
    {
        "id": "inner_voice",
        "name": "心の声の過多",
        "desc": "1シーンに心の声（括弧書きの内面描写）が2つ以上入っていないか",
    },
    {
        "id": "repetition",
        "name": "内容の繰り返し",
        "desc": "同じ内容・同じ表現を繰り返していないか",
    },
    {
        "id": "trigger",
        "name": "覚悟トリガー",
        "desc": "主人公の覚悟シーンに具体物トリガー（手紙・写真・形見など）があるか",
    },
    {
        "id": "villain_pattern",
        "name": "悪役の攻撃パターン",
        "desc": "悪役の攻撃・嫌がらせパターンが一本調子でなく変化があるか",
    },
    {
        "id": "sound_effects",
        "name": "効果音",
        "desc": "効果音（SE指示やオノマトペ）が適切に入っているか",
    },
]


def _build_check_prompt(script: str) -> tuple[str, str]:
    """チェック用のプロンプトを構築する

    Args:
        script: 台本テキスト

    Returns:
        (system_prompt, user_prompt) のタプル
    """
    # チェック項目リストをテキスト化
    items_text = "\n".join(
        f'{i+1}. [{c["id"]}] {c["name"]}: {c["desc"]}'
        for i, c in enumerate(CHECK_ITEMS)
    )

    system_prompt = (
        "あなたはスカッと動画の台本を専門的にチェックする編集者です。\n"
        "以下のチェック項目に基づいて台本を厳密に評価してください。\n"
        "各項目について合否判定と、不合格の場合は具体的な問題箇所を指摘してください。"
    )

    user_prompt = (
        f"【チェック項目】\n{items_text}\n\n"
        f"【台本】\n{script}\n\n"
        "【出力形式】以下のJSON形式で返してください:\n"
        '{"items": [\n'
        '  {"id": "contrast", "passed": true, "details": "", "locations": []},\n'
        '  {"id": "senses", "passed": false, "details": "五感描写が視覚のみ", '
        '"locations": ["3行目付近: 彼女は青い服を着ていた"]}\n'
        '], "summary": "全体の評価コメント"}'
    )
    return system_prompt, user_prompt


def check_script(script: str, loop_number: int) -> CheckReport:
    """台本をチェック項目に基づいて評価する

    Args:
        script: 台本テキスト
        loop_number: 何回目のチェックか

    Returns:
        チェック結果レポート
    """
    logger.info("台本チェック開始（%d回目）", loop_number)
    system_prompt, user_prompt = _build_check_prompt(script)

    try:
        result = call_claude_json(system_prompt, user_prompt)
    except Exception as e:
        logger.error("チェックAPI呼び出し失敗: %s", e)
        raise

    return _parse_check_result(result, loop_number)


def _parse_check_result(
    data: dict, loop_number: int
) -> CheckReport:
    """APIレスポンスのJSONをCheckReportに変換する

    Args:
        data: Claude APIからのJSON応答
        loop_number: チェック回数

    Returns:
        パース済みのCheckReport
    """
    report = CheckReport(loop_number=loop_number)
    report.summary = data.get("summary", "")

    # チェック項目名のマッピング（id → name）
    id_to_name = {c["id"]: c["name"] for c in CHECK_ITEMS}

    for item_data in data.get("items", []):
        item_id = item_data.get("id", "unknown")
        item = CheckItem(
            name=id_to_name.get(item_id, item_id),
            passed=item_data.get("passed", False),
            details=item_data.get("details", ""),
            locations=item_data.get("locations", []),
        )
        report.items.append(item)

    logger.info(
        "チェック結果: %d/%d 合格",
        report.passed_count,
        len(report.items),
    )
    return report


def _build_fix_prompt(
    script: str, report: CheckReport
) -> tuple[str, str]:
    """修正用プロンプトを構築する

    Args:
        script: 現在の台本テキスト
        report: 不合格項目を含むチェック結果

    Returns:
        (system_prompt, user_prompt) のタプル
    """
    # 不合格項目だけ抽出
    failed_items = [i for i in report.items if not i.passed]
    issues = "\n".join(
        f"- {item.name}: {item.details}" for item in failed_items
    )

    system_prompt = (
        "あなたはスカッと動画の台本を修正する専門家です。\n"
        "指摘された問題点を修正した台本を出力してください。\n"
        "台本の全体的な流れやキャラクターは変えないでください。\n"
        "修正した台本のテキストのみを返してください。\n"
        "説明や前置きは不要です。"
    )

    user_prompt = (
        f"【修正すべき問題点】\n{issues}\n\n"
        f"【現在の台本】\n{script}\n\n"
        "上記の問題点を修正した台本全文を出力してください。"
    )
    return system_prompt, user_prompt


def fix_script(script: str, report: CheckReport) -> str:
    """不合格項目を修正した台本を生成する

    Args:
        script: 現在の台本テキスト
        report: チェック結果

    Returns:
        修正された台本テキスト
    """
    logger.info(
        "台本修正開始（不合格: %d項目）", report.failed_count
    )
    system_prompt, user_prompt = _build_fix_prompt(script, report)

    try:
        fixed = call_claude(system_prompt, user_prompt)
        logger.info("台本修正完了（%d文字）", len(fixed))
        return fixed
    except Exception as e:
        logger.error("修正API呼び出し失敗: %s", e)
        raise


def run_check_fix_loop(script: str) -> tuple[str, list[CheckReport]]:
    """チェック→修正のループを最大MAX_LOOPS回実行する

    Args:
        script: 元の台本テキスト

    Returns:
        (最終台本, チェック結果リスト) のタプル
    """
    current_script = script
    reports: list[CheckReport] = []

    for i in range(1, MAX_LOOPS + 1):
        logger.info("=== ループ %d/%d ===", i, MAX_LOOPS)

        # チェック実行
        report = check_script(current_script, i)
        reports.append(report)

        # 全合格なら終了
        if report.all_passed:
            logger.info("全項目合格！ループ終了")
            break

        # 最終ループなら修正せずに終了
        if i == MAX_LOOPS:
            logger.warning(
                "最大ループ回数に達しました（残り不合格: %d項目）",
                report.failed_count,
            )
            break

        # 修正実行
        current_script = fix_script(current_script, report)

    return current_script, reports
