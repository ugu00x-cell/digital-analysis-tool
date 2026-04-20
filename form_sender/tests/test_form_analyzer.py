"""utils/form_analyzer.py のテスト"""

import pytest
from bs4 import BeautifulSoup

from utils.form_analyzer import (
    analyze_form_bs4,
    check_robots_txt,
    classify_field,
    detect_captcha,
    find_contact_url,
)


# --- classify_field テスト ---

class TestClassifyField:
    """フィールド分類のテスト"""

    def test_email_type(self) -> None:
        """type=emailはemail判定される"""
        html = '<input type="email" name="mail">'
        elem = BeautifulSoup(html, "html.parser").find("input")
        assert classify_field(elem) == "email"

    def test_tel_type(self) -> None:
        """type=telはphone判定される"""
        html = '<input type="tel" name="tel">'
        elem = BeautifulSoup(html, "html.parser").find("input")
        assert classify_field(elem) == "phone"

    def test_textarea_is_message(self) -> None:
        """textareaはmessage判定される"""
        html = '<textarea name="body"></textarea>'
        elem = BeautifulSoup(html, "html.parser").find("textarea")
        assert classify_field(elem) == "message"

    def test_company_by_name(self) -> None:
        """name属性から会社名を判定"""
        html = '<input type="text" name="company">'
        elem = BeautifulSoup(html, "html.parser").find("input")
        assert classify_field(elem) == "company"

    def test_last_name_pattern(self) -> None:
        """姓のパターンマッチ"""
        html = '<input type="text" name="last_name">'
        elem = BeautifulSoup(html, "html.parser").find("input")
        assert classify_field(elem) == "last_name"

    def test_postal_pattern(self) -> None:
        """郵便番号のパターンマッチ"""
        html = '<input type="text" placeholder="郵便番号">'
        elem = BeautifulSoup(html, "html.parser").find("input")
        assert classify_field(elem) == "postal"

    def test_unknown_field(self) -> None:
        """不明フィールドはNone"""
        html = '<input type="text" name="xyz_field_999">'
        elem = BeautifulSoup(html, "html.parser").find("input")
        assert classify_field(elem) is None


# --- analyze_form_bs4 テスト ---

class TestAnalyzeForm:
    """フォーム解析のテスト"""

    def test_basic_form(self) -> None:
        """基本的なフォームの解析"""
        html = """
        <form>
            <input type="text" name="company" />
            <input type="email" name="email" />
            <textarea name="message"></textarea>
            <input type="submit" value="送信" />
        </form>
        """
        form = BeautifulSoup(html, "html.parser").find("form")
        mapping = analyze_form_bs4(form)
        assert "company" in mapping
        assert "email" in mapping
        assert "message" in mapping

    def test_hidden_fields_skipped(self) -> None:
        """hiddenフィールドは除外される"""
        html = """
        <form>
            <input type="hidden" name="token" value="abc" />
            <input type="email" name="email" />
        </form>
        """
        form = BeautifulSoup(html, "html.parser").find("form")
        mapping = analyze_form_bs4(form)
        assert "email" in mapping
        assert len(mapping) == 1


# --- detect_captcha テスト ---

class TestDetectCaptcha:
    """CAPTCHA検出のテスト"""

    def test_recaptcha(self) -> None:
        """reCAPTCHAを検出"""
        html = '<div class="g-recaptcha" data-sitekey="xxx"></div>'
        assert detect_captcha(html) is True

    def test_no_captcha(self) -> None:
        """CAPTCHAなし"""
        html = "<form><input type=text></form>"
        assert detect_captcha(html) is False

    def test_turnstile(self) -> None:
        """Cloudflare Turnstileを検出"""
        html = '<div class="cf-turnstile"></div>'
        assert detect_captcha(html) is True


# --- find_contact_url テスト ---

class TestFindContactUrl:
    """お問い合わせURL検出のテスト"""

    def test_found(self) -> None:
        """お問い合わせリンクを発見"""
        html = '<a href="/contact">お問い合わせ</a>'
        result = find_contact_url(html, "https://example.com")
        assert result == "https://example.com/contact"

    def test_not_found(self) -> None:
        """リンクなしでNone"""
        html = "<a href='/about'>会社概要</a>"
        result = find_contact_url(html, "https://example.com")
        assert result is None


# --- check_robots_txt テスト ---

class TestCheckRobotsTxt:
    """robots.txtチェックのテスト"""

    def test_nonexistent_allows(self) -> None:
        """robots.txt不在なら許可"""
        # 存在しないドメイン → requests例外 → 許可扱い
        result = check_robots_txt("https://this-domain-does-not-exist-xyz.com")
        assert result is True
