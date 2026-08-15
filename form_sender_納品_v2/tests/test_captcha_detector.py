"""テスト - utils/captcha_detector.py

各関数に正常系2・異常系2・境界値1で計5ケース。
"""

from utils.captcha_detector import (
    detect_captcha_info,
    _detect_recaptcha_v2,
    _detect_recaptcha_v3,
    _detect_hcaptcha,
    _detect_turnstile,
)
from bs4 import BeautifulSoup


# === detect_captcha_info: 全体統合テスト ===

class TestDetectCaptchaInfo:

    def test_recaptcha_v2_detected(self):
        """正常系: reCAPTCHA v2 HTMLから正しく抽出"""
        html = '<html><body><div class="g-recaptcha" data-sitekey="6Lc_sitekey_abc"></div></body></html>'
        result = detect_captcha_info(html)
        assert result["present"] is True
        assert result["type"] == "recaptcha_v2"
        assert result["sitekey"] == "6Lc_sitekey_abc"

    def test_hcaptcha_detected(self):
        """正常系: hCaptchaが検出される"""
        html = '<html><body><div class="h-captcha" data-sitekey="hc_sitekey_xyz"></div></body></html>'
        result = detect_captcha_info(html)
        assert result["present"] is True
        assert result["type"] == "hcaptcha"
        assert result["sitekey"] == "hc_sitekey_xyz"

    def test_captcha_word_but_no_sitekey(self):
        """異常系: CAPTCHAキーワードだけあってsitekey抽出不可"""
        html = '<html><body><div class="g-recaptcha"></div></body></html>'
        result = detect_captcha_info(html)
        assert result["present"] is True
        assert result["type"] == "unknown"

    def test_empty_html(self):
        """異常系: 空文字HTMLは何も返さない"""
        result = detect_captcha_info("")
        assert result["present"] is False
        assert result["type"] is None

    def test_no_captcha_in_html(self):
        """境界値: CAPTCHAなしの通常ページ"""
        html = "<html><body><form><input type='text'></form></body></html>"
        result = detect_captcha_info(html)
        assert result["present"] is False


# === _detect_recaptcha_v2 ===

class TestDetectRecaptchaV2:

    def test_valid_sitekey(self):
        """正常系: 有効なsitekeyを抽出"""
        soup = BeautifulSoup(
            '<div class="g-recaptcha" data-sitekey="key123"></div>',
            "html.parser",
        )
        result = _detect_recaptcha_v2(soup)
        assert result is not None
        assert result["sitekey"] == "key123"

    def test_multiple_classes(self):
        """正常系: 複数classの中から検出"""
        soup = BeautifulSoup(
            '<div class="g-recaptcha custom-class" data-sitekey="multi"></div>',
            "html.parser",
        )
        result = _detect_recaptcha_v2(soup)
        assert result["sitekey"] == "multi"

    def test_no_class(self):
        """異常系: g-recaptchaクラスなし"""
        soup = BeautifulSoup('<div data-sitekey="abc"></div>', "html.parser")
        assert _detect_recaptcha_v2(soup) is None

    def test_empty_sitekey(self):
        """異常系: sitekey属性が空"""
        soup = BeautifulSoup(
            '<div class="g-recaptcha" data-sitekey=""></div>',
            "html.parser",
        )
        assert _detect_recaptcha_v2(soup) is None

    def test_boundary_only_class_no_attr(self):
        """境界値: classのみでdata-sitekey属性なし"""
        soup = BeautifulSoup('<div class="g-recaptcha"></div>', "html.parser")
        assert _detect_recaptcha_v2(soup) is None


# === _detect_hcaptcha ===

class TestDetectHcaptcha:

    def test_valid_hcaptcha(self):
        """正常系: hCaptcha検出"""
        soup = BeautifulSoup(
            '<div class="h-captcha" data-sitekey="hkey"></div>',
            "html.parser",
        )
        result = _detect_hcaptcha(soup)
        assert result["type"] == "hcaptcha"

    def test_with_other_classes(self):
        """正常系: 他のクラスと混在"""
        soup = BeautifulSoup(
            '<div class="h-captcha foo bar" data-sitekey="abc"></div>',
            "html.parser",
        )
        assert _detect_hcaptcha(soup)["sitekey"] == "abc"

    def test_no_h_captcha_class(self):
        """異常系: h-captchaクラスなし"""
        soup = BeautifulSoup('<div data-sitekey="x"></div>', "html.parser")
        assert _detect_hcaptcha(soup) is None

    def test_no_sitekey(self):
        """異常系: data-sitekey属性なし"""
        soup = BeautifulSoup('<div class="h-captcha"></div>', "html.parser")
        assert _detect_hcaptcha(soup) is None

    def test_boundary_empty_html(self):
        """境界値: 空HTML"""
        soup = BeautifulSoup("", "html.parser")
        assert _detect_hcaptcha(soup) is None


# === _detect_turnstile ===

class TestDetectTurnstile:

    def test_valid_turnstile(self):
        """正常系: Turnstile検出"""
        soup = BeautifulSoup(
            '<div class="cf-turnstile" data-sitekey="tskey"></div>',
            "html.parser",
        )
        result = _detect_turnstile(soup)
        assert result["type"] == "turnstile"
        assert result["sitekey"] == "tskey"

    def test_nested_element(self):
        """正常系: ネストされた要素で検出"""
        soup = BeautifulSoup(
            '<form><div class="cf-turnstile" data-sitekey="nested"></div></form>',
            "html.parser",
        )
        assert _detect_turnstile(soup)["sitekey"] == "nested"

    def test_no_turnstile(self):
        """異常系: Turnstileクラスなし"""
        soup = BeautifulSoup('<div class="captcha"></div>', "html.parser")
        assert _detect_turnstile(soup) is None

    def test_empty_sitekey(self):
        """異常系: 空のsitekey"""
        soup = BeautifulSoup(
            '<div class="cf-turnstile" data-sitekey=""></div>',
            "html.parser",
        )
        assert _detect_turnstile(soup) is None

    def test_boundary_similar_class(self):
        """境界値: 似た名前のclassは誤検出しない"""
        soup = BeautifulSoup(
            '<div class="cf-turnstile-widget"></div>', "html.parser"
        )
        # find(class_="cf-turnstile")は完全一致のみ検出するため該当なし
        assert _detect_turnstile(soup) is None


# === _detect_recaptcha_v3 ===

class TestDetectRecaptchaV3:

    def test_basic_execute_call(self):
        """正常系: grecaptcha.executeの基本パターン"""
        html = '<script>grecaptcha.execute("6Lcv3_sitekey_long_enough", {action: "submit"})</script>'
        result = _detect_recaptcha_v3(html)
        assert result["type"] == "recaptcha_v3"
        assert result["sitekey"] == "6Lcv3_sitekey_long_enough"
        assert result["action"] == "submit"

    def test_single_quote_pattern(self):
        """正常系: シングルクォートパターン"""
        html = "grecaptcha.execute('sitekey_value_abcdefg', {action:'homepage'})"
        result = _detect_recaptcha_v3(html)
        assert result["sitekey"] == "sitekey_value_abcdefg"
        assert result["action"] == "homepage"

    def test_no_execute_call(self):
        """異常系: grecaptcha.executeがないHTML"""
        html = "<html><body>No captcha</body></html>"
        assert _detect_recaptcha_v3(html) is None

    def test_sitekey_too_short(self):
        """異常系: sitekeyが短すぎる（{20,}に満たない）"""
        html = 'grecaptcha.execute("short", {action:"x"})'
        assert _detect_recaptcha_v3(html) is None

    def test_boundary_action_missing(self):
        """境界値: actionパラメータがない場合のデフォルト"""
        html = 'grecaptcha.execute("sitekey_long_enough_12345")'
        result = _detect_recaptcha_v3(html)
        assert result is not None
        assert result["action"] == "submit"  # デフォルト
        assert result["min_score"] == 0.3
