"""テスト - db_templates モジュール
正常系2・異常系2・境界値1 を各関数で満たす
"""

import pytest

from utils.db import init_db
from utils.db_templates import save_template, get_templates, delete_template


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """テスト用DBを一時ディレクトリに作成する"""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("utils.db.DB_PATH", test_db)
    init_db()
    yield test_db


# === save_template: 正常系2 + 異常系2 + 境界値1 ===

class TestSaveTemplate:

    def test_new_template_returns_id(self):
        """正常系: 新規テンプレートでIDが返る"""
        tid = save_template("挨拶", "こんにちは{{company_name}}様")
        assert tid > 0

    def test_new_template_persists(self):
        """正常系: 保存した本文がDBに永続化される"""
        tid = save_template("営業テンプレ", "ご連絡です")
        templates = get_templates()
        assert any(t["id"] == tid and t["body"] == "ご連絡です" for t in templates)

    def test_update_template(self):
        """正常系（更新）: 既存テンプレートの上書き"""
        tid = save_template("旧名", "旧本文")
        save_template("新名", "新本文", tid=tid)
        templates = get_templates()
        assert len(templates) == 1
        assert templates[0]["name"] == "新名"
        assert templates[0]["body"] == "新本文"

    def test_empty_body_saves(self):
        """異常系: 本文空文字でも保存できる"""
        tid = save_template("空テンプレ", "")
        assert tid > 0

    def test_duplicate_name_saves(self):
        """異常系: 同名テンプレートも別IDで保存される"""
        t1 = save_template("同名", "本文A")
        t2 = save_template("同名", "本文B")
        assert t1 != t2
        assert len(get_templates()) == 2

    def test_boundary_long_body(self):
        """境界値: 長文本文の保存"""
        long_body = "あ" * 10000
        tid = save_template("長文", long_body)
        templates = get_templates()
        assert any(t["body"] == long_body for t in templates)


# === get_templates: 正常系2 + 異常系2 + 境界値1 ===

class TestGetTemplates:

    def test_empty_returns_empty(self):
        """正常系: テンプレートなしは空リスト"""
        assert get_templates() == []

    def test_multiple_templates(self):
        """正常系: 複数テンプレート取得"""
        save_template("A", "body A")
        save_template("B", "body B")
        save_template("C", "body C")
        assert len(get_templates()) == 3

    def test_returns_list_of_dicts(self):
        """異常系確認: 戻り値がlist[dict]型"""
        save_template("X", "Y")
        result = get_templates()
        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    def test_has_created_at(self):
        """異常系確認: created_atフィールドが含まれる"""
        save_template("日時テスト", "body")
        tmpl = get_templates()[0]
        assert "created_at" in tmpl
        assert tmpl["created_at"] != ""

    def test_single_template(self):
        """境界値: 1件だけの場合"""
        save_template("唯一", "body")
        assert len(get_templates()) == 1


# === delete_template: 正常系2 + 異常系2 + 境界値1 ===

class TestDeleteTemplate:

    def test_delete_existing(self):
        """正常系: 既存テンプレート削除"""
        tid = save_template("削除対象", "body")
        delete_template(tid)
        assert get_templates() == []

    def test_delete_one_keeps_others(self):
        """正常系: 1件削除しても他は残る"""
        t1 = save_template("残す", "a")
        t2 = save_template("消す", "b")
        delete_template(t2)
        templates = get_templates()
        assert len(templates) == 1
        assert templates[0]["id"] == t1

    def test_delete_nonexistent_no_error(self):
        """異常系: 存在しないID削除でもエラーなし"""
        delete_template(9999)

    def test_double_delete_no_error(self):
        """異常系: 二重削除でもエラーなし"""
        tid = save_template("二重", "body")
        delete_template(tid)
        delete_template(tid)

    def test_delete_id_zero(self):
        """境界値: ID=0の削除"""
        delete_template(0)
