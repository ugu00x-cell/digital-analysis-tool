"""テスト - db_profiles モジュール
正常系2・異常系2・境界値1 を各関数で満たす
"""

import pytest

from utils.db import init_db
from utils.db_profiles import save_profile, get_profiles, get_profile, delete_profile


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """テスト用DBを一時ディレクトリに作成する"""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("utils.db.DB_PATH", test_db)
    init_db()
    yield test_db


# === save_profile: 正常系2 + 異常系2 + 境界値1 ===

class TestSaveProfile:

    def test_new_profile_returns_id(self):
        """正常系: 新規プロファイル保存でIDが返る"""
        pid = save_profile({"name": "太郎", "email": "t@e.com"})
        assert pid > 0

    def test_new_profile_persists(self):
        """正常系: 保存データがDBに永続化される"""
        pid = save_profile({
            "name": "テスト", "last_name": "山田", "first_name": "太郎",
            "email": "test@example.com", "company": "テスト株式会社",
        })
        prof = get_profile(pid)
        assert prof["last_name"] == "山田"
        assert prof["company"] == "テスト株式会社"

    def test_update_existing_profile(self):
        """正常系（更新）: 既存プロファイルの上書き"""
        pid = save_profile({"name": "旧"})
        save_profile({"id": pid, "name": "新", "email": "new@e.com"})
        prof = get_profile(pid)
        assert prof["name"] == "新"
        assert prof["email"] == "new@e.com"

    def test_empty_name_saves(self):
        """異常系: name空文字でも保存できる（DB制約なし）"""
        pid = save_profile({"name": ""})
        assert pid > 0

    def test_missing_optional_fields_default_empty(self):
        """異常系: 省略フィールドは空文字になる"""
        pid = save_profile({"name": "最小"})
        prof = get_profile(pid)
        assert prof["phone"] == ""
        assert prof["address"] == ""
        assert prof["postal"] == ""
        assert prof["last_kana"] == ""

    def test_boundary_all_fields_filled(self):
        """境界値: 全フィールドを埋めて保存"""
        data = {
            "name": "A", "last_name": "B", "first_name": "C",
            "last_kana": "D", "first_kana": "E", "company": "F",
            "email": "G", "phone": "H", "postal": "I", "address": "J",
        }
        pid = save_profile(data)
        prof = get_profile(pid)
        for key, val in data.items():
            assert prof[key] == val


# === get_profiles: 正常系2 + 異常系2 + 境界値1 ===

class TestGetProfiles:

    def test_empty_db_returns_empty(self):
        """正常系: 空DBでは空リスト"""
        assert get_profiles() == []

    def test_multiple_profiles_ordered(self):
        """正常系: 複数件がID昇順で返る"""
        save_profile({"name": "C"})
        save_profile({"name": "A"})
        save_profile({"name": "B"})
        profiles = get_profiles()
        assert len(profiles) == 3
        assert profiles[0]["name"] == "C"

    def test_returns_list_of_dicts(self):
        """異常系確認: 戻り値がlist[dict]型"""
        save_profile({"name": "X"})
        result = get_profiles()
        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    def test_deleted_profile_not_in_list(self):
        """異常系: 削除済みプロファイルは含まれない"""
        pid = save_profile({"name": "削除用"})
        delete_profile(pid)
        assert len(get_profiles()) == 0

    def test_single_profile(self):
        """境界値: 1件だけの場合"""
        save_profile({"name": "唯一"})
        profiles = get_profiles()
        assert len(profiles) == 1


# === get_profile: 正常系2 + 異常系2 + 境界値1 ===

class TestGetProfile:

    def test_existing_profile(self):
        """正常系: 存在するIDでプロファイル取得"""
        pid = save_profile({"name": "取得テスト"})
        prof = get_profile(pid)
        assert prof["name"] == "取得テスト"

    def test_returns_all_fields(self):
        """正常系: 全フィールドが辞書に含まれる"""
        pid = save_profile({"name": "フィールドテスト", "email": "a@b.c"})
        prof = get_profile(pid)
        expected_keys = {"id", "name", "last_name", "first_name",
                         "last_kana", "first_kana", "company",
                         "email", "phone", "postal", "address"}
        assert expected_keys.issubset(prof.keys())

    def test_nonexistent_id_returns_none(self):
        """異常系: 存在しないIDはNone"""
        assert get_profile(9999) is None

    def test_deleted_id_returns_none(self):
        """異常系: 削除済みIDはNone"""
        pid = save_profile({"name": "削除対象"})
        delete_profile(pid)
        assert get_profile(pid) is None

    def test_first_id_is_one(self):
        """境界値: 最初のIDは1"""
        pid = save_profile({"name": "最初"})
        assert pid == 1
        assert get_profile(1) is not None


# === delete_profile: 正常系2 + 異常系2 + 境界値1 ===

class TestDeleteProfile:

    def test_delete_existing(self):
        """正常系: 既存プロファイルの削除"""
        pid = save_profile({"name": "削除"})
        delete_profile(pid)
        assert get_profile(pid) is None

    def test_delete_one_keeps_others(self):
        """正常系: 1件削除しても他は残る"""
        p1 = save_profile({"name": "残す"})
        p2 = save_profile({"name": "消す"})
        delete_profile(p2)
        assert get_profile(p1) is not None
        assert len(get_profiles()) == 1

    def test_delete_nonexistent_no_error(self):
        """異常系: 存在しないID削除でもエラーにならない"""
        delete_profile(9999)

    def test_double_delete_no_error(self):
        """異常系: 同一IDの二重削除でもエラーにならない"""
        pid = save_profile({"name": "二重削除"})
        delete_profile(pid)
        delete_profile(pid)

    def test_delete_id_zero(self):
        """境界値: ID=0の削除（存在しない）"""
        delete_profile(0)
