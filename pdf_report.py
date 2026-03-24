"""
PDF レポート生成モジュール
企業デジタル分析ツール用

必要なライブラリ:
    pip install reportlab
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
import io
import math
import os

# ===== カラー定数 =====
COLOR_PRIMARY = HexColor("#0ea5e9")
COLOR_DARK = HexColor("#0f172a")
COLOR_TEXT = HexColor("#1e293b")
COLOR_SUB = HexColor("#64748b")
COLOR_BORDER = HexColor("#e2e8f0")
COLOR_BG_LIGHT = HexColor("#f8fafc")
COLOR_RED = HexColor("#dc2626")
COLOR_ORANGE = HexColor("#ea580c")
COLOR_YELLOW = HexColor("#d97706")
COLOR_BLUE = HexColor("#2563eb")
COLOR_GREEN = HexColor("#16a34a")
COLOR_WHITE = HexColor("#ffffff")

RANK_COLORS = {"s": COLOR_RED, "a": COLOR_ORANGE, "b": COLOR_YELLOW, "c": COLOR_BLUE, "d": COLOR_GREEN}

# ===== 日本語フォント検出 =====
def get_japanese_font():
    """利用可能な日本語フォントを検出して登録する"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # よくあるフォントパス（Windows / Mac / Linux）
    font_candidates = [
        # Windows
        ("C:/Windows/Fonts/meiryo.ttc", "Meiryo"),
        ("C:/Windows/Fonts/msgothic.ttc", "MSGothic"),
        ("C:/Windows/Fonts/YuGothM.ttc", "YuGothic"),
        ("C:/Windows/Fonts/msmincho.ttc", "MSMincho"),
        # Mac
        ("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", "HiraginoSans"),
        ("/Library/Fonts/Arial Unicode.ttf", "ArialUnicode"),
        # Linux
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
        ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
    ]

    for path, name in font_candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue

    # フォントが見つからない場合はHelveticaを使う（日本語は文字化けする）
    return "Helvetica"


# ===== ユーティリティ =====
def draw_rounded_rect(c, x, y, w, h, radius=3*mm, fill_color=None, stroke_color=None):
    """角丸四角を描画"""
    c.saveState()
    if fill_color:
        c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(0.5)
    else:
        c.setStrokeColor(fill_color or COLOR_WHITE)

    p = c.beginPath()
    p.roundRect(x, y, w, h, radius)
    p.close()

    if fill_color and stroke_color:
        c.drawPath(p, fill=1, stroke=1)
    elif fill_color:
        c.drawPath(p, fill=1, stroke=0)
    elif stroke_color:
        c.drawPath(p, fill=0, stroke=1)

    c.restoreState()


def draw_text(c, x, y, text, font, size, color=COLOR_TEXT):
    """テキスト描画ヘルパー"""
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, str(text))


def draw_text_right(c, x, y, text, font, size, color=COLOR_TEXT):
    """右寄せテキスト"""
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawRightString(x, y, str(text))


def draw_progress_bar(c, x, y, width, height, pct, bar_color):
    """プログレスバー描画"""
    # 背景
    draw_rounded_rect(c, x, y, width, height, radius=height/2, fill_color=HexColor("#f1f5f9"))
    # バー
    if pct > 0:
        bar_w = max(width * pct, height)  # 最低でも丸くなる幅
        draw_rounded_rect(c, x, y, bar_w, height, radius=height/2, fill_color=bar_color)


def draw_radar_chart(c, cx, cy, radius, details):
    """レーダーチャートをPDF上に描画"""
    categories = []
    for name, pts, max_pts, _ in details:
        pct = pts / max_pts if max_pts > 0 else 0
        short = name.replace("コンテンツ充実度", "コンテンツ").replace("問い合わせ導線", "問い合わせ")
        categories.append({"name": short, "pct": pct})

    n = len(categories)
    offset = -math.pi / 2

    # 背景グリッド
    for lv in [0.25, 0.5, 0.75, 1.0]:
        r = radius * lv
        c.setStrokeColor(COLOR_BORDER)
        c.setLineWidth(0.3)
        c.circle(cx, cy, r, stroke=1, fill=0)

    # 軸線
    for i in range(n):
        angle = offset + (2 * math.pi * i / n)
        x2 = cx + radius * math.cos(angle)
        y2 = cy + radius * math.sin(angle)
        c.setStrokeColor(COLOR_BORDER)
        c.setLineWidth(0.3)
        c.line(cx, cy, x2, y2)

    # データポリゴン
    points = []
    for i, cat in enumerate(categories):
        angle = offset + (2 * math.pi * i / n)
        r = radius * cat["pct"]
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))

    if points:
        p = c.beginPath()
        p.moveTo(points[0][0], points[0][1])
        for pt in points[1:]:
            p.lineTo(pt[0], pt[1])
        p.close()
        c.setFillColor(HexColor("#0ea5e9"))
        c.setFillAlpha(0.15)
        c.setStrokeColor(COLOR_PRIMARY)
        c.setLineWidth(1.5)
        c.drawPath(p, fill=1, stroke=1)
        c.setFillAlpha(1.0)

    # ドット
    for pt in points:
        c.setFillColor(COLOR_PRIMARY)
        c.circle(pt[0], pt[1], 2.5, stroke=0, fill=1)

    # ラベル
    font = get_japanese_font()
    for i, cat in enumerate(categories):
        angle = offset + (2 * math.pi * i / n)
        lr = radius + 12*mm
        lx = cx + lr * math.cos(angle)
        ly = cy + lr * math.sin(angle)
        c.setFont(font, 7)
        c.setFillColor(COLOR_SUB)
        if math.cos(angle) > 0.3:
            c.drawString(lx, ly - 3, cat["name"])
        elif math.cos(angle) < -0.3:
            c.drawRightString(lx, ly - 3, cat["name"])
        else:
            c.drawCentredString(lx, ly - 3, cat["name"])


# ===== メイン: PDFレポート生成 =====
def generate_report_pdf(result):
    """
    分析結果からPDFレポートを生成し、bytesを返す。

    Args:
        result: run_analysis() の戻り値（dict）

    Returns:
        bytes: PDF のバイトデータ
    """
    buf = io.BytesIO()
    width, height = A4  # 595 x 842 pt
    margin = 20 * mm
    font = get_japanese_font()

    cv = canvas.Canvas(buf, pagesize=A4)
    cv.setTitle(f"デジタル分析レポート - {result['domain']}")
    cv.setAuthor("企業デジタル分析ツール")

    # ===== ページ1: メインレポート =====

    # --- ヘッダー帯 ---
    draw_rounded_rect(cv, margin, height - 45*mm, width - 2*margin, 30*mm, radius=4*mm, fill_color=COLOR_DARK)
    draw_text(cv, margin + 8*mm, height - 25*mm, "📊 企業デジタル分析レポート", font, 16, COLOR_WHITE)
    draw_text(cv, margin + 8*mm, height - 33*mm, f"対象: {result['url']}", font, 8, HexColor("#94a3b8"))
    draw_text_right(cv, width - margin - 8*mm, height - 25*mm, f"分析日: {result['analyzed_at']}", font, 8, HexColor("#94a3b8"))

    # --- スコア・ランク・業種 カード ---
    card_y = height - 75*mm
    card_h = 22*mm
    card_w = (width - 2*margin - 8*mm) / 3

    # スコアカード
    draw_rounded_rect(cv, margin, card_y, card_w, card_h, radius=3*mm, fill_color=COLOR_WHITE, stroke_color=COLOR_BORDER)
    draw_text(cv, margin + 5*mm, card_y + card_h - 7*mm, "総合スコア", font, 7, COLOR_SUB)
    rc = result["rank_class"]
    draw_text(cv, margin + 5*mm, card_y + 4*mm, f"{result['score']} / 100", font, 18, RANK_COLORS.get(rc, COLOR_TEXT))

    # ランクカード
    x2 = margin + card_w + 4*mm
    draw_rounded_rect(cv, x2, card_y, card_w, card_h, radius=3*mm, fill_color=COLOR_WHITE, stroke_color=COLOR_BORDER)
    draw_text(cv, x2 + 5*mm, card_y + card_h - 7*mm, "営業ランク", font, 7, COLOR_SUB)
    draw_text(cv, x2 + 5*mm, card_y + 4*mm, f"{result['rank']}  {result['rank_label']}", font, 14, RANK_COLORS.get(rc, COLOR_TEXT))

    # 業種カード
    x3 = margin + 2*(card_w + 4*mm) - 4*mm
    draw_rounded_rect(cv, x3, card_y, card_w, card_h, radius=3*mm, fill_color=COLOR_WHITE, stroke_color=COLOR_BORDER)
    draw_text(cv, x3 + 5*mm, card_y + card_h - 7*mm, "推定業種", font, 7, COLOR_SUB)
    draw_text(cv, x3 + 5*mm, card_y + 4*mm, result["category"], font, 14, COLOR_TEXT)

    # --- 判定メッセージ ---
    msg_y = card_y - 12*mm
    score = result["score"]
    if score <= 40:
        draw_rounded_rect(cv, margin, msg_y, width - 2*margin, 8*mm, radius=2*mm, fill_color=HexColor("#fee2e2"))
        draw_text(cv, margin + 5*mm, msg_y + 2*mm, f"🎯 営業対象です！ スコア{score}点 → Web改善の提案余地が大きい企業です", font, 8, HexColor("#991b1b"))
    elif score <= 55:
        draw_rounded_rect(cv, margin, msg_y, width - 2*margin, 8*mm, radius=2*mm, fill_color=HexColor("#fef3c7"))
        draw_text(cv, margin + 5*mm, msg_y + 2*mm, f"⚠️ 要検討 スコア{score}点 → 部分的に改善提案が可能です", font, 8, HexColor("#92400e"))
    else:
        draw_rounded_rect(cv, margin, msg_y, width - 2*mm, 8*mm, radius=2*mm, fill_color=HexColor("#dcfce7"))
        draw_text(cv, margin + 5*mm, msg_y + 2*mm, f"✅ 対象外 スコア{score}点 → デジタル施策が充実しています", font, 8, HexColor("#166534"))

    # --- レーダーチャート + スコア内訳 ---
    section_y = msg_y - 8*mm

    # レーダーチャート（左側）
    draw_text(cv, margin, section_y, "スコアレーダー", font, 10, COLOR_TEXT)
    radar_cx = margin + 55*mm
    radar_cy = section_y - 48*mm
    draw_radar_chart(cv, radar_cx, radar_cy, 35*mm, result["details"])

    # スコア内訳（右側）
    right_x = width / 2 + 5*mm
    draw_text(cv, right_x, section_y, "スコア内訳", font, 10, COLOR_TEXT)

    icons = ["🔒", "🔍", "📱", "📄", "📞", "⚙️", "👥"]
    item_y = section_y - 12*mm
    for i, (name, pts, mx, status) in enumerate(result["details"]):
        pct = pts / mx if mx > 0 else 0

        # 項目名
        draw_text(cv, right_x, item_y, f"{name}", font, 8, COLOR_TEXT)

        # プログレスバー
        bar_x = right_x
        bar_y = item_y - 5*mm
        bar_w = 55*mm
        bar_color = COLOR_GREEN if pct >= 0.7 else (HexColor("#f59e0b") if pct >= 0.4 else COLOR_RED)
        draw_progress_bar(cv, bar_x, bar_y, bar_w, 3*mm, pct, bar_color)

        # スコア値
        draw_text_right(cv, right_x + 75*mm, item_y, f"{pts} / {mx}", font, 8, COLOR_SUB)

        item_y -= 13*mm

    # --- 詳細セクション ---
    detail_y = section_y - 105*mm

    # SEO
    draw_rounded_rect(cv, margin, detail_y - 55*mm, (width - 2*margin - 4*mm)/2, 60*mm, radius=3*mm, fill_color=COLOR_BG_LIGHT, stroke_color=COLOR_BORDER)
    dy = detail_y
    draw_text(cv, margin + 5*mm, dy, "🔍 SEO分析", font, 9, COLOR_TEXT)
    seo = result["seo"]
    seo_items = [
        ("タイトル", f"{seo['title'][:25] or '（なし）'}（{seo['title_length']}文字）"),
        ("meta description", f"{'あり' if seo['description_length']>0 else 'なし'}（{seo['description_length']}文字）"),
        ("モバイル対応", "✅対応" if seo["has_viewport"] else "❌未対応"),
        ("OGP設定", "✅あり" if seo["has_ogp"] else "❌なし"),
        ("H1タグ", f"{seo['h1_count']}個"),
        ("canonical", "✅あり" if seo["has_canonical"] else "❌なし"),
        ("favicon", "✅あり" if seo["has_favicon"] else "❌なし"),
    ]
    for label, value in seo_items:
        dy -= 7*mm
        draw_text(cv, margin + 5*mm, dy, label, font, 7, COLOR_SUB)
        draw_text_right(cv, margin + (width - 2*margin - 4*mm)/2 - 3*mm, dy, value, font, 7, COLOR_TEXT)

    # リンク構造
    rx = margin + (width - 2*margin - 4*mm)/2 + 4*mm
    draw_rounded_rect(cv, rx, detail_y - 55*mm, (width - 2*margin - 4*mm)/2, 60*mm, radius=3*mm, fill_color=COLOR_BG_LIGHT, stroke_color=COLOR_BORDER)
    dy = detail_y
    draw_text(cv, rx + 5*mm, dy, "🔗 リンク・問い合わせ", font, 9, COLOR_TEXT)
    lnk = result["links"]; cnt = result["contact"]
    link_items = [
        ("総リンク数", str(lnk["total_links"])),
        ("内部 / 外部", f"{lnk['internal_links']} / {lnk['external_links']}"),
        ("SNS連携", f"{lnk['sns_count']}件" + (f"（{', '.join(lnk['sns_links'].keys())}）" if lnk['sns_links'] else "")),
        ("採用ページ", "✅あり" if lnk["recruit_found"] else "❌なし"),
        ("問い合わせフォーム", "✅あり" if cnt["has_form"] else "❌なし"),
        ("電話番号", f"✅{cnt['phone_number']}" if cnt["has_phone"] else "❌なし"),
        ("メールリンク", "✅あり" if cnt["has_email_link"] else "❌なし"),
    ]
    for label, value in link_items:
        dy -= 7*mm
        draw_text(cv, rx + 5*mm, dy, label, font, 7, COLOR_SUB)
        # 長いテキストを切り詰め
        draw_text_right(cv, rx + (width - 2*margin - 4*mm)/2 - 3*mm, dy, value[:30], font, 7, COLOR_TEXT)

    # --- フッター ---
    cv.setFont(font, 6)
    cv.setFillColor(COLOR_SUB)
    cv.drawCentredString(width/2, 12*mm, f"企業デジタル分析ツール v3.0 | Generated: {result['analyzed_at']} | {result['url']}")

    cv.save()
    buf.seek(0)
    return buf.getvalue()


# ===== 一括分析用サマリーPDF =====
def generate_batch_summary_pdf(results):
    """
    一括分析結果のサマリーPDFを生成

    Args:
        results: list of run_analysis() の戻り値

    Returns:
        bytes: PDF のバイトデータ
    """
    buf = io.BytesIO()
    width, height = A4
    margin = 20 * mm
    font = get_japanese_font()

    cv = canvas.Canvas(buf, pagesize=A4)
    cv.setTitle("一括分析サマリーレポート")

    # ヘッダー
    draw_rounded_rect(cv, margin, height - 40*mm, width - 2*margin, 25*mm, radius=4*mm, fill_color=COLOR_DARK)
    draw_text(cv, margin + 8*mm, height - 23*mm, "📊 一括分析サマリーレポート", font, 16, COLOR_WHITE)
    draw_text(cv, margin + 8*mm, height - 31*mm, f"分析件数: {len(results)}件 | 生成日: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", font, 8, HexColor("#94a3b8"))

    # サマリー
    targets = [r for r in results if r["score"] <= 40]
    maybes = [r for r in results if 40 < r["score"] <= 55]
    safes = [r for r in results if r["score"] > 55]
    avg = sum(r["score"] for r in results) / len(results) if results else 0

    sy = height - 55*mm
    cw = (width - 2*margin - 12*mm) / 4
    labels = [("営業対象", len(targets), COLOR_RED), ("要検討", len(maybes), COLOR_YELLOW), ("対象外", len(safes), COLOR_GREEN), ("平均スコア", f"{avg:.0f}", COLOR_BLUE)]
    for i, (label, val, color) in enumerate(labels):
        x = margin + i*(cw + 4*mm)
        draw_rounded_rect(cv, x, sy, cw, 15*mm, radius=3*mm, fill_color=COLOR_WHITE, stroke_color=COLOR_BORDER)
        draw_text(cv, x + 5*mm, sy + 9*mm, str(val), font, 16, color)
        draw_text(cv, x + 5*mm, sy + 3*mm, label, font, 7, COLOR_SUB)

    # テーブル
    table_y = sy - 12*mm
    draw_text(cv, margin, table_y, "分析結果一覧（スコア昇順）", font, 10, COLOR_TEXT)

    # ヘッダー行
    table_y -= 8*mm
    draw_rounded_rect(cv, margin, table_y - 1*mm, width - 2*margin, 7*mm, radius=0, fill_color=COLOR_DARK)
    headers = ["ランク", "スコア", "URL", "判定", "業種", "SNS", "採用"]
    col_x = [margin+3*mm, margin+18*mm, margin+35*mm, margin+95*mm, margin+125*mm, margin+148*mm, margin+162*mm]
    for i, h in enumerate(headers):
        draw_text(cv, col_x[i], table_y + 1*mm, h, font, 7, COLOR_WHITE)

    # データ行
    sorted_results = sorted(results, key=lambda x: x["score"])
    row_y = table_y - 7*mm
    for j, r in enumerate(sorted_results):
        if row_y < 20*mm:
            # 新しいページ
            cv.showPage()
            row_y = height - 30*mm
            draw_rounded_rect(cv, margin, row_y + 1*mm, width - 2*margin, 7*mm, radius=0, fill_color=COLOR_DARK)
            for i, h in enumerate(headers):
                draw_text(cv, col_x[i], row_y + 3*mm, h, font, 7, COLOR_WHITE)
            row_y -= 7*mm

        # 交互背景
        if j % 2 == 0:
            draw_rounded_rect(cv, margin, row_y - 1*mm, width - 2*margin, 7*mm, radius=0, fill_color=COLOR_BG_LIGHT)

        rc = r["rank_class"]
        draw_text(cv, col_x[0], row_y + 1*mm, r["rank"], font, 8, RANK_COLORS.get(rc, COLOR_TEXT))
        draw_text(cv, col_x[1], row_y + 1*mm, str(r["score"]), font, 8, RANK_COLORS.get(rc, COLOR_TEXT))
        draw_text(cv, col_x[2], row_y + 1*mm, r["domain"][:30], font, 7, COLOR_TEXT)
        draw_text(cv, col_x[3], row_y + 1*mm, r["rank_label"][:10], font, 7, COLOR_TEXT)
        draw_text(cv, col_x[4], row_y + 1*mm, r["category"], font, 7, COLOR_TEXT)
        draw_text(cv, col_x[5], row_y + 1*mm, str(r["links"]["sns_count"]), font, 7, COLOR_TEXT)
        draw_text(cv, col_x[6], row_y + 1*mm, "✅" if r["links"]["recruit_found"] else "❌", font, 7, COLOR_TEXT)

        row_y -= 7*mm

    # フッター
    cv.setFont(font, 6)
    cv.setFillColor(COLOR_SUB)
    cv.drawCentredString(width/2, 10*mm, f"企業デジタル分析ツール v3.0 | Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    cv.save()
    buf.seek(0)
    return buf.getvalue()


# datetimeのインポート（generate_batch_summary_pdfで使用）
import datetime
