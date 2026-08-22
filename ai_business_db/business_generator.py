"""AIスモールビジネス情報の収集・HTML生成（叩き台版）。

実際のスクレイピングの前に、ダミーデータでHTML生成の仕組みを検証する。
"""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# 出力ディレクトリ
DB_DIR = Path(__file__).resolve().parent / "business_data"


def ensure_db_dir() -> None:
    """business_dataディレクトリが存在しない場合は作成する。

    Raises:
        OSError: ディレクトリ作成に失敗した場合。
    """
    try:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"ビジネスDBディレクトリを確認: {DB_DIR}")
    except OSError as e:
        logger.error(f"business_dataディレクトリの作成に失敗しました: {e}")
        raise


def generate_mock_businesses() -> list[dict]:
    """ダミーのAIスモールビジネス情報を生成する。

    Returns:
        list[dict]: ビジネス情報の辞書リスト。各要素は以下のキーを持つ:
            - id (int): ビジネスID
            - name (str): 企業・プロジェクト名
            - model (str): ビジネスモデル説明
            - source (str): 情報源
            - date (str): 掲載日付
    """
    mock_data = [
        {
            "id": 1,
            "name": "AIWritingAssistant",
            "model": "AI技術を使用したライティング補助ツール。個人ユーザー向けにSaaS展開。",
            "source": "TechCrunch",
            "date": "2026-08-01",
        },
        {
            "id": 2,
            "name": "SmartFarmingAI",
            "model": "農業データ分析AI。センサーデータから収穫予測を実施。",
            "source": "AgTech Digest",
            "date": "2026-07-28",
        },
        {
            "id": 3,
            "name": "LocalMarketingBot",
            "model": "小売店向けのマーケティング自動化。SNS投稿を自動生成。",
            "source": "Small Business Weekly",
            "date": "2026-07-15",
        },
        {
            "id": 4,
            "name": "VoiceHealthAdvisor",
            "model": "音声入力による健康相談AI。医学知識ベースに基づく。",
            "source": "HealthTech News",
            "date": "2026-07-10",
        },
        {
            "id": 5,
            "name": "CodeReviewGPT",
            "model": "プログラマー向けのコード審査AI。本番環境のセキュリティ問題を検出。",
            "source": "Dev Tools Weekly",
            "date": "2026-06-30",
        },
    ]
    return mock_data


def generate_html_for_business(business: dict) -> str:
    """ビジネス情報をHTML形式に変換する。

    Args:
        business: ビジネス情報の辞書。

    Returns:
        str: HTML形式のテキスト。
    """
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{business['name']} - AIスモールビジネス情報</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .container {{
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .metadata {{
            color: #666;
            font-size: 0.9em;
            margin: 20px 0;
        }}
        .model {{
            background-color: #ecf0f1;
            padding: 15px;
            border-left: 4px solid #3498db;
            margin: 20px 0;
        }}
        .source {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 0.9em;
            color: #666;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{business['name']}</h1>

        <div class="metadata">
            <p><strong>ID:</strong> {business['id']}</p>
            <p><strong>掲載日:</strong> {business['date']}</p>
        </div>

        <h2>ビジネスモデル</h2>
        <div class="model">
            {business['model']}
        </div>

        <div class="source">
            <strong>情報源:</strong> {business['source']}
        </div>

        <div style="margin-top: 40px; text-align: center;">
            <a href="index.html">← 全事例に戻る</a>
        </div>
    </div>
</body>
</html>
"""
    return html


def save_business_html(business: dict) -> Path:
    """ビジネス情報をHTMLファイルとして保存する。

    Args:
        business: ビジネス情報の辞書。

    Returns:
        Path: 保存したファイルのパス。

    Raises:
        OSError: ファイル書き込みに失敗した場合。
    """
    ensure_db_dir()

    html_content = generate_html_for_business(business)
    file_name = f"{business['id']:03d}_{business['name'].lower().replace(' ', '-')}.html"
    file_path = DB_DIR / file_name

    try:
        file_path.write_text(html_content, encoding="utf-8")
        logger.info(f"HTMLファイルを保存しました: {file_path}")
        return file_path
    except OSError as e:
        logger.error(f"HTMLファイルの保存に失敗しました: {e}")
        raise


def generate_index_html(businesses: list[dict]) -> str:
    """全ビジネス情報へのインデックスページをHTML形式で生成する。

    Args:
        businesses: ビジネス情報の辞書リスト。

    Returns:
        str: インデックスのHTML形式テキスト。
    """
    business_links = "\n".join(
        f'        <li><a href="{b["id"]:03d}_{b["name"].lower().replace(" ", "-")}.html">{b["name"]}</a> - {b["date"]}</li>'
        for b in businesses
    )

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIスモールビジネス情報データベース</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            background-color: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #667eea;
            text-align: center;
            margin-bottom: 10px;
        }}
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 30px;
        }}
        ul {{
            list-style: none;
            padding: 0;
        }}
        li {{
            padding: 12px 15px;
            margin: 10px 0;
            background-color: #f8f9fa;
            border-left: 4px solid #667eea;
            border-radius: 4px;
        }}
        a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 0.9em;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 AIスモールビジネス情報データベース</h1>
        <div class="subtitle">世界中のAI技術を活用した小規模ビジネス事例を集約</div>

        <h2>掲載事例 ({len(businesses)}件)</h2>
        <ul>
{business_links}
        </ul>

        <div class="footer">
            <p>最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
    </div>
</body>
</html>
"""
    return html


def export_all_businesses() -> Path:
    """全ビジネス情報をHTML形式で生成・保存する。

    Returns:
        Path: インデックスファイルのパス。
    """
    ensure_db_dir()

    # ダミーデータを生成
    businesses = generate_mock_businesses()
    logger.info(f"ビジネス情報を生成しました: {len(businesses)}件")

    # 各ビジネスのHTMLを個別保存
    for business in businesses:
        save_business_html(business)

    # インデックスページを生成・保存
    index_html = generate_index_html(businesses)
    index_path = DB_DIR / "index.html"

    try:
        index_path.write_text(index_html, encoding="utf-8")
        logger.info(f"インデックスページを保存しました: {index_path}")
        return index_path
    except OSError as e:
        logger.error(f"インデックスページの保存に失敗しました: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    export_all_businesses()
