"""CMS/フォームプラグイン検出 - サイトのCMSを判定しフィールドマッピングを生成

WordPress Contact Form 7、MW WP Form等の主要CMSプラグインを検出し、
プラグイン固有のフィールド命名規則からマッピングを自動生成する。
"""

import logging
from typing import Optional

from bs4 import Tag

logger = logging.getLogger(__name__)

# CMS/プラグイン定義
# detect: HTML内で検索するシグネチャ文字列
# field_rules: name属性のキーワード → フィールドタイプの対応
CMS_SIGNATURES: dict[str, dict] = {
    "wpcf7": {
        "detect": ["wpcf7-form", "wpcf7-text", "wpcf7-email"],
        "field_rules": {
            "your-name": "name",
            "your-email": "email",
            "your-message": "message",
            "your-subject": "subject",
            "your-tel": "phone",
            "your-company": "company",
            "your-address": "address",
        },
    },
    "mw_wp_form": {
        "detect": ["mw_wp_form", "mwform-"],
        "field_rules": {
            "name": "name",
            "email": "email",
            "tel": "phone",
            "message": "message",
            "company": "company",
            "address": "address",
            "zip": "postal",
        },
    },
    "snow_monkey": {
        "detect": ["smf-", "snow-monkey-form"],
        "field_rules": {
            "name": "name",
            "email": "email",
            "tel": "phone",
            "message": "message",
        },
    },
    "gravity_forms": {
        "detect": ["gform_wrapper", "gform_body", "ginput_"],
        "field_rules": {
            "input_": "name",  # Gravity Formsは番号式（input_1, input_2等）
        },
    },
}


def detect_cms(html: str) -> Optional[str]:
    """HTMLからCMS/フォームプラグインを検出する

    Args:
        html: ページのHTMLテキスト

    Returns:
        CMS種別名、検出できなければNone
    """
    html_lower = html.lower()

    for cms_name, config in CMS_SIGNATURES.items():
        for signature in config["detect"]:
            if signature in html_lower:
                logger.info("CMS検出: %s (シグネチャ: %s)", cms_name, signature)
                return cms_name

    return None


def get_cms_field_mapping(cms_type: str, form: Tag) -> dict[str, dict]:
    """CMS種別に基づいてフィールドマッピングを生成する

    CMS固有のname属性パターンからフィールドタイプを推定する。

    Args:
        cms_type: detect_cms()で検出されたCMS種別名
        form: form要素

    Returns:
        {フィールドタイプ: {name, tag, type, source}} のマッピング
    """
    config = CMS_SIGNATURES.get(cms_type)
    if not config:
        return {}

    rules = config["field_rules"]
    mapping: dict[str, dict] = {}
    skip_types = {"hidden", "submit", "button", "image", "reset"}

    for elem in form.find_all(["input", "textarea", "select"]):
        input_type = elem.get("type", "text")
        if input_type in skip_types:
            continue

        name = elem.get("name", "")
        if not name:
            continue

        field_type = _match_cms_rules(name, rules, elem)
        if field_type and field_type not in mapping:
            mapping[field_type] = {
                "name": name,
                "tag": elem.name,
                "type": input_type,
                "source": f"cms:{cms_type}",
            }

    logger.info("CMS[%s]マッピング: %s", cms_type, list(mapping.keys()))
    return mapping


def _match_cms_rules(name: str, rules: dict, elem: Tag) -> Optional[str]:
    """name属性をCMSルールでマッチングする"""
    name_lower = name.lower()

    # 完全一致 or 部分一致でルール検索
    for rule_key, field_type in rules.items():
        if rule_key in name_lower:
            return field_type

    # type属性によるフォールバック判定
    if elem.get("type") == "email":
        return "email"
    if elem.get("type") == "tel":
        return "phone"
    if elem.name == "textarea":
        return "message"

    return None


def try_cms_mapping(html: str, form: Tag) -> Optional[dict]:
    """CMS検出からマッピング生成まで一括で実行する

    Args:
        html: ページのHTMLテキスト
        form: form要素

    Returns:
        CMS検出時はマッピング辞書、未検出ならNone
    """
    cms_type = detect_cms(html)
    if not cms_type:
        return None

    mapping = get_cms_field_mapping(cms_type, form)
    if not mapping:
        return None

    return mapping
