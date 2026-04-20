"""scraper.py のユニットテスト"""

import pytest
from bs4 import BeautifulSoup

from engine.scraper import (
    analyze_form,
    classify_field,
    detect_captcha,
    extract_forms,
    find_contact_url,
)


# テスト用HTML
FORM_HTML = """
<form action="/contact" method="post">
  <label for="corp">会社名</label>
  <input type="text" name="company_name" id="corp">
  <label for="nm">お名前</label>
  <input type="text" name="your-name" id="nm" placeholder="お名前">
  <input type="email" name="email" placeholder="メールアドレス">
  <input type="tel" name="phone">
  <input type="text" name="subject" placeholder="件名">
  <textarea name="message" placeholder="お問い合わせ内容"></textarea>
  <input type="submit" value="送信">
</form>
"""

LINK_HTML = """
<html><body>
  <a href="/about">会社概要</a>
  <a href="/contact">お問い合わせ</a>
  <a href="/products">製品一覧</a>
</body></html>
"""


class TestFindContactUrl:
    """お問い合わせURL検出のテスト"""

    def test_find_contact_link(self) -> None:
        """正常系：お問い合わせリンクが見つかる"""
        url = find_contact_url(LINK_HTML, "https://example.com")
        assert url == "https://example.com/contact"

    def test_no_contact_link(self) -> None:
        """正常系：リンクが見つからない場合はNone"""
        html = "<html><a href='/about'>会社概要</a></html>"
        assert find_contact_url(html, "https://example.com") is None


class TestExtractForms:
    """フォーム要素抽出のテスト"""

    def test_extract_single_form(self) -> None:
        """正常系：1つのフォームを抽出"""
        forms = extract_forms(FORM_HTML)
        assert len(forms) == 1

    def test_no_forms(self) -> None:
        """正常系：フォームなし"""
        forms = extract_forms("<html><body>no form</body></html>")
        assert len(forms) == 0


class TestClassifyField:
    """フィールド分類のテスト"""

    def test_email_by_type(self) -> None:
        """正常系：type=emailで判定"""
        soup = BeautifulSoup('<input type="email" name="addr">', "html.parser")
        assert classify_field(soup.find("input")) == "email"

    def test_tel_by_type(self) -> None:
        """正常系：type=telで判定"""
        soup = BeautifulSoup('<input type="tel" name="num">', "html.parser")
        assert classify_field(soup.find("input")) == "phone"

    def test_textarea_is_message(self) -> None:
        """正常系：textareaはmessage"""
        soup = BeautifulSoup("<textarea name='body'></textarea>", "html.parser")
        assert classify_field(soup.find("textarea")) == "message"

    def test_company_by_name(self) -> None:
        """正常系：name属性で会社名を判定"""
        soup = BeautifulSoup('<input type="text" name="company">', "html.parser")
        assert classify_field(soup.find("input")) == "company"

    def test_unknown_field(self) -> None:
        """境界値：判定不能ならNone"""
        soup = BeautifulSoup('<input type="text" name="xyz123">', "html.parser")
        assert classify_field(soup.find("input")) is None


class TestAnalyzeForm:
    """フォーム全体解析のテスト"""

    def test_full_form_analysis(self) -> None:
        """正常系：全フィールドが正しくマッピングされる"""
        soup = BeautifulSoup(FORM_HTML, "html.parser")
        form = soup.find("form")
        mapping = analyze_form(form)

        assert "email" in mapping
        assert "message" in mapping
        assert "phone" in mapping
        assert mapping["email"]["name"] == "email"

    def test_empty_form(self) -> None:
        """異常系：空のフォーム"""
        soup = BeautifulSoup("<form></form>", "html.parser")
        mapping = analyze_form(soup.find("form"))
        assert mapping == {}


class TestDetectCaptcha:
    """CAPTCHA検出のテスト"""

    def test_recaptcha_detected(self) -> None:
        """正常系：reCAPTCHA検出"""
        html = '<div class="g-recaptcha"></div>'
        assert detect_captcha(html) is True

    def test_no_captcha(self) -> None:
        """正常系：CAPTCHAなし"""
        assert detect_captcha("<form><input></form>") is False

    def test_turnstile_detected(self) -> None:
        """正常系：Cloudflare Turnstile検出"""
        html = '<div class="cf-turnstile"></div>'
        assert detect_captcha(html) is True
