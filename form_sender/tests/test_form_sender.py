"""テスト - utils/form_sender.py
正常系2・異常系2・境界値1 を各関数で満たす
"""

import pytest
from bs4 import BeautifulSoup

from utils.form_sender import (
    random_wait,
    _detect_spa,
    _detect_iframe_form,
    _detect_file_upload,
    USER_AGENTS,
    TYPE_DELAY_MIN,
    TYPE_DELAY_MAX,
    FIELD_MOVE_MIN,
    FIELD_MOVE_MAX,
    PRE_SUBMIT_MIN,
    PRE_SUBMIT_MAX,
)
from config import WAIT_MIN, WAIT_MAX


# === random_wait（レガシー動作）: 正常系2 + 異常系2 + 境界値1 ===

class TestRandomWaitLegacy:

    def test_within_range(self):
        """正常系: 引数なしでWAIT_MIN〜WAIT_MAX範囲内"""
        for _ in range(20):
            wait = random_wait()
            assert WAIT_MIN <= wait <= WAIT_MAX

    def test_returns_float(self):
        """正常系: 戻り値はfloat型"""
        assert isinstance(random_wait(), float)

    def test_not_always_same(self):
        """異常系確認: 毎回同じ値にならない（ランダム性）"""
        values = {random_wait() for _ in range(10)}
        assert len(values) > 1

    def test_positive_value(self):
        """異常系確認: 常に正の値"""
        for _ in range(10):
            assert random_wait() > 0

    def test_boundary_reasonable_range(self):
        """境界値: 分散が適切（0秒や1000秒にならない）"""
        wait = random_wait()
        assert wait >= 10
        assert wait <= 200


# === random_wait（base_interval指定）: 正常系2 + 異常系2 + 境界値1 ===

class TestRandomWaitWithInterval:

    def test_within_multiplied_range(self):
        """正常系: base_interval指定時、0.8x〜1.5xの範囲内"""
        base = 10.0
        for _ in range(50):
            wait = random_wait(base_interval=base)
            assert base * 0.8 <= wait <= base * 1.5

    def test_different_base_values(self):
        """正常系: 異なるbase_intervalで異なる範囲"""
        wait_small = [random_wait(base_interval=5.0) for _ in range(20)]
        wait_large = [random_wait(base_interval=100.0) for _ in range(20)]
        # 小さいbaseの最大値は大きいbaseの最小値より小さいはず
        assert max(wait_small) < min(wait_large)

    def test_not_always_same_with_interval(self):
        """異常系確認: 同じbase_intervalでもランダム"""
        values = {random_wait(base_interval=10.0) for _ in range(10)}
        assert len(values) > 1

    def test_positive_with_small_interval(self):
        """異常系確認: 小さい値でも正の値"""
        for _ in range(10):
            assert random_wait(base_interval=1.0) > 0

    def test_boundary_exact_range(self):
        """境界値: base=10秒→8〜15秒の範囲に収まる"""
        base = 10.0
        for _ in range(100):
            wait = random_wait(base_interval=base)
            assert 8.0 <= wait <= 15.0


# === USER_AGENTS定数: 正常系2 + 異常系2 + 境界値1 ===

class TestUserAgents:

    def test_has_entries(self):
        """正常系: UAリストにエントリが存在する"""
        assert len(USER_AGENTS) >= 4

    def test_all_strings(self):
        """正常系: 全エントリがstr型"""
        for ua in USER_AGENTS:
            assert isinstance(ua, str)

    def test_contains_chrome_windows(self):
        """異常系確認: Chrome Windows UAが含まれる"""
        assert any("Windows" in ua and "Chrome" in ua and "Edg" not in ua
                    for ua in USER_AGENTS)

    def test_contains_firefox(self):
        """異常系確認: Firefox UAが含まれる"""
        assert any("Firefox" in ua for ua in USER_AGENTS)

    def test_boundary_not_empty_strings(self):
        """境界値: 空文字のUAがない"""
        for ua in USER_AGENTS:
            assert len(ua) > 20


# === タイピング・待機定数: 正常系2 + 異常系2 + 境界値1 ===

class TestHumanLikeConstants:

    def test_type_delay_range_valid(self):
        """正常系: タイピング遅延の範囲が正しい"""
        assert TYPE_DELAY_MIN == 20
        assert TYPE_DELAY_MAX == 80

    def test_field_move_range_valid(self):
        """正常系: フィールド移動待機の範囲が正しい"""
        assert FIELD_MOVE_MIN == 0.1
        assert FIELD_MOVE_MAX == 0.3

    def test_pre_submit_range_valid(self):
        """異常系確認: 送信前待機の範囲が正しい"""
        assert PRE_SUBMIT_MIN == 0.5
        assert PRE_SUBMIT_MAX == 1.5

    def test_delay_min_less_than_max(self):
        """異常系確認: MIN < MAX が全ペアで成立"""
        assert TYPE_DELAY_MIN < TYPE_DELAY_MAX
        assert FIELD_MOVE_MIN < FIELD_MOVE_MAX
        assert PRE_SUBMIT_MIN < PRE_SUBMIT_MAX

    def test_boundary_all_positive(self):
        """境界値: 全定数が正の値"""
        for val in [TYPE_DELAY_MIN, TYPE_DELAY_MAX,
                    FIELD_MOVE_MIN, FIELD_MOVE_MAX,
                    PRE_SUBMIT_MIN, PRE_SUBMIT_MAX]:
            assert val > 0


# === _detect_spa: 正常系2 + 異常系2 + 境界値1 ===

class TestDetectSpa:

    def test_normal_html_not_spa(self):
        """正常系: 通常HTMLはSPAとして検出されない"""
        html = "<html><body><p>" + "テキスト" * 100 + "</p></body></html>"
        assert _detect_spa(html) is False

    def test_spa_page_detected(self):
        """正常系: script多数＋テキスト少ないHTMLはSPA検出"""
        scripts = "".join(f"<script src='app{i}.js'></script>" for i in range(10))
        html = f"<html><body><div id='root'></div>{scripts}</body></html>"
        assert _detect_spa(html) is True

    def test_no_body_tag(self):
        """異常系: bodyなしはFalse"""
        assert _detect_spa("<html></html>") is False

    def test_empty_html(self):
        """異常系: 空HTMLはFalse"""
        assert _detect_spa("") is False

    def test_boundary_few_scripts_with_text(self):
        """境界値: scriptありだがテキスト十分→SPA判定しない"""
        text = "あ" * 200
        html = f"<html><body><p>{text}</p><script src='a.js'></script></body></html>"
        assert _detect_spa(html) is False


# === _detect_iframe_form: 正常系2 + 異常系2 + 境界値1 ===

class TestDetectIframeForm:

    def test_google_form(self):
        """正常系: Google Forms iframe検出"""
        html = '<html><body><iframe src="https://forms.google.com/abc"></iframe></body></html>'
        assert _detect_iframe_form(html) is True

    def test_typeform(self):
        """正常系: Typeform iframe検出"""
        html = '<html><body><iframe src="https://example.typeform.com/to/xyz"></iframe></body></html>'
        assert _detect_iframe_form(html) is True

    def test_normal_iframe_not_detected(self):
        """異常系: 通常iframeは検出されない"""
        html = '<iframe src="https://example.com/page"></iframe>'
        assert _detect_iframe_form(html) is False

    def test_no_iframe(self):
        """異常系: iframeなし"""
        html = "<html><body><p>test</p></body></html>"
        assert _detect_iframe_form(html) is False

    def test_boundary_hubspot_form(self):
        """境界値: HubSpot フォーム検出"""
        html = '<iframe src="https://share.hubspot.com/form/abc"></iframe>'
        assert _detect_iframe_form(html) is True


# === _detect_file_upload: 正常系2 + 異常系2 + 境界値1 ===

class TestDetectFileUpload:

    def test_required_file_input(self):
        """正常系: required付きファイルフィールド検出"""
        form_html = '<form><input type="file" required></form>'
        form = BeautifulSoup(form_html, "html.parser").find("form")
        assert _detect_file_upload(form) is True

    def test_required_with_name(self):
        """正常系: name付きrequiredファイルフィールド"""
        form_html = '<form><input type="file" name="resume" required></form>'
        form = BeautifulSoup(form_html, "html.parser").find("form")
        assert _detect_file_upload(form) is True

    def test_optional_file_not_detected(self):
        """異常系: required無しファイルフィールドは検出しない"""
        form_html = '<form><input type="file"></form>'
        form = BeautifulSoup(form_html, "html.parser").find("form")
        assert _detect_file_upload(form) is False

    def test_no_file_input(self):
        """異常系: ファイルフィールドなし"""
        form_html = '<form><input type="text" name="name"><textarea name="msg"></textarea></form>'
        form = BeautifulSoup(form_html, "html.parser").find("form")
        assert _detect_file_upload(form) is False

    def test_boundary_mixed_inputs(self):
        """境界値: ファイル＋テキスト混在、ファイルは任意"""
        form_html = """<form>
            <input type="text" name="name" required>
            <input type="file" name="attachment">
            <textarea name="msg" required></textarea>
        </form>"""
        form = BeautifulSoup(form_html, "html.parser").find("form")
        assert _detect_file_upload(form) is False
