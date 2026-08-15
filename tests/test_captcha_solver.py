"""テスト - utils/captcha_solver.py

ネットワーク呼び出しはmockで代替。
Playwright Pageもunittest.mock.Mockで代用。
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# テスト用にDB_PATHを一時ファイルに差し替え
import utils.db as db_module

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
db_module.DB_PATH = Path(_tmp.name)
_tmp.close()

from utils.captcha_solver import (  # noqa: E402
    solve_captcha,
    _submit_captcha,
    _poll_result,
    _inject_token,
    _map_error,
    _increment_usage_counters,
    _safe_int,
    _safe_float,
    COST_JPY_PER_SOLVE,
)
from utils.db import init_db  # noqa: E402
from utils.db_logs import get_setting  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    """各テスト前にDBを初期化する"""
    conn = sqlite3.connect(str(db_module.DB_PATH))
    conn.execute("DROP TABLE IF EXISTS settings")
    conn.execute("DROP TABLE IF EXISTS form_cache")
    conn.execute("DROP TABLE IF EXISTS send_logs")
    conn.commit()
    conn.close()
    init_db()
    yield


# === _map_error ===

class TestMapError:

    def test_wrong_key(self):
        """正常系: ERROR_WRONG_USER_KEYマッピング"""
        assert _map_error("ERROR_WRONG_USER_KEY") == "api_key_invalid"

    def test_zero_balance(self):
        """正常系: ERROR_ZERO_BALANCEマッピング"""
        assert _map_error("ERROR_ZERO_BALANCE") == "insufficient_balance"

    def test_unknown_error(self):
        """異常系: 未知のエラーコード"""
        assert _map_error("RANDOM_CODE").startswith("api_error:")

    def test_empty_string(self):
        """異常系: 空文字列"""
        assert _map_error("") == "api_error:"

    def test_boundary_queue_full(self):
        """境界値: queue_full（リトライ対象）"""
        assert _map_error("ERROR_NO_SLOT_AVAILABLE") == "queue_full"


# === _safe_int / _safe_float ===

class TestSafeConverters:

    def test_safe_int_valid(self):
        """正常系: 有効な数字文字列"""
        assert _safe_int("42") == 42

    def test_safe_int_invalid(self):
        """異常系: 無効な文字列は0"""
        assert _safe_int("abc") == 0

    def test_safe_float_valid(self):
        """正常系: 有効な小数文字列"""
        assert _safe_float("3.14") == 3.14

    def test_safe_float_invalid(self):
        """異常系: 無効な文字列は0.0"""
        assert _safe_float("xyz") == 0.0

    def test_boundary_empty_string(self):
        """境界値: 空文字列"""
        assert _safe_int("") == 0
        assert _safe_float("") == 0.0


# === _increment_usage_counters ===

class TestIncrementUsageCounters:

    def test_first_call_creates_counter(self):
        """正常系: 初回呼び出しでカウンタ作成"""
        _increment_usage_counters(0.45)
        assert _safe_int(get_setting("captcha_solve_count_total", "0")) == 1

    def test_multiple_calls_accumulate(self):
        """正常系: 複数回で累積"""
        _increment_usage_counters(0.45)
        _increment_usage_counters(0.45)
        total = _safe_int(get_setting("captcha_solve_count_total", "0"))
        spend = _safe_float(get_setting("captcha_spend_jpy", "0"))
        assert total == 2
        assert abs(spend - 0.9) < 0.001

    def test_corrupt_value_recovers(self):
        """異常系: 破損した値（"abc"）からの復旧"""
        from utils.db_logs import save_setting
        save_setting("captcha_solve_count_total", "corrupt")
        _increment_usage_counters(0.45)
        assert _safe_int(get_setting("captcha_solve_count_total", "0")) == 1

    def test_zero_cost(self):
        """異常系: コスト0でも呼び出せる"""
        _increment_usage_counters(0.0)
        assert _safe_int(get_setting("captcha_solve_count_total", "0")) == 1

    def test_boundary_large_cost(self):
        """境界値: 大きなコスト値"""
        _increment_usage_counters(1000.0)
        assert _safe_float(get_setting("captcha_spend_jpy", "0")) == 1000.0


# === _inject_token ===

class TestInjectToken:

    def test_recaptcha_v2_injection(self):
        """正常系: reCAPTCHA v2トークン注入"""
        page = MagicMock()
        _inject_token(page, {"type": "recaptcha_v2"}, "test_token")
        assert page.evaluate.called

    def test_hcaptcha_injection(self):
        """正常系: hCaptchaトークン注入"""
        page = MagicMock()
        _inject_token(page, {"type": "hcaptcha"}, "hc_token")
        assert page.evaluate.called

    def test_unknown_type_raises(self):
        """異常系: 不明なtypeはValueError"""
        page = MagicMock()
        with pytest.raises(ValueError):
            _inject_token(page, {"type": "weird"}, "token")

    def test_empty_token_raises(self):
        """異常系: 空トークンはValueError"""
        page = MagicMock()
        with pytest.raises(ValueError):
            _inject_token(page, {"type": "recaptcha_v2"}, "")

    def test_boundary_turnstile(self):
        """境界値: Turnstile注入"""
        page = MagicMock()
        _inject_token(page, {"type": "turnstile"}, "ts_token")
        assert page.evaluate.called


# === _submit_captcha ===

class TestSubmitCaptcha:

    def test_successful_submit_v2(self):
        """正常系: reCAPTCHA v2のタスク登録成功"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": 1, "request": "12345"}
        with patch("utils.captcha_solver.requests.post", return_value=mock_resp):
            result = _submit_captcha(
                "api_key", "http://example.com",
                {"type": "recaptcha_v2", "sitekey": "sk"},
            )
        assert result == "12345"

    def test_successful_submit_hcaptcha(self):
        """正常系: hCaptchaタスク登録成功"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": 1, "request": "hc_id"}
        with patch("utils.captcha_solver.requests.post", return_value=mock_resp):
            result = _submit_captcha(
                "api_key", "http://example.com",
                {"type": "hcaptcha", "sitekey": "hs"},
            )
        assert result == "hc_id"

    def test_invalid_api_key(self):
        """異常系: 無効なAPIキーで例外"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": 0, "request": "ERROR_WRONG_USER_KEY",
        }
        with patch("utils.captcha_solver.requests.post", return_value=mock_resp):
            with pytest.raises(ValueError, match="api_key_invalid"):
                _submit_captcha(
                    "bad_key", "http://example.com",
                    {"type": "recaptcha_v2", "sitekey": "sk"},
                )

    def test_unsupported_captcha_type(self):
        """異常系: 未対応のCAPTCHA種別"""
        with pytest.raises(ValueError, match="unsupported_captcha_type"):
            _submit_captcha(
                "api_key", "http://example.com",
                {"type": "funcaptcha", "sitekey": "sk"},
            )

    def test_boundary_zero_balance(self):
        """境界値: 残高切れエラー"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": 0, "request": "ERROR_ZERO_BALANCE",
        }
        with patch("utils.captcha_solver.requests.post", return_value=mock_resp):
            with pytest.raises(ValueError, match="insufficient_balance"):
                _submit_captcha(
                    "api_key", "http://example.com",
                    {"type": "recaptcha_v2", "sitekey": "sk"},
                )


# === solve_captcha 統合テスト ===

class TestSolveCaptcha:

    def test_no_sitekey_returns_error(self):
        """正常系: sitekeyなしは早期return"""
        page = MagicMock()
        result = solve_captcha(page, "http://x.com", {"type": "recaptcha_v2"})
        assert result["solved"] is False
        assert result["error"] == "no_sitekey"

    def test_no_api_key_returns_error(self):
        """正常系: APIキー未設定で早期return"""
        page = MagicMock()
        with patch("utils.captcha_solver._get_api_key", return_value=""):
            result = solve_captcha(
                page, "http://x.com",
                {"type": "recaptcha_v2", "sitekey": "abc"},
            )
        assert result["solved"] is False
        assert result["error"] == "no_api_key"

    def test_full_success_flow(self):
        """正常系: APIキーあり→登録→ポーリング→注入の全フロー"""
        page = MagicMock()
        submit_resp = MagicMock()
        submit_resp.json.return_value = {"status": 1, "request": "id1"}
        poll_resp = MagicMock()
        poll_resp.json.return_value = {"status": 1, "request": "TOKEN_OK"}

        with patch("utils.captcha_solver._get_api_key", return_value="KEY"), \
             patch("utils.captcha_solver.requests.post", return_value=submit_resp), \
             patch("utils.captcha_solver.requests.get", return_value=poll_resp), \
             patch("utils.captcha_solver.time.sleep"):
            result = solve_captcha(
                page, "http://x.com",
                {"type": "recaptcha_v2", "sitekey": "abc"},
            )

        assert result["solved"] is True
        assert result["token"] == "TOKEN_OK"
        assert result["cost_jpy"] == COST_JPY_PER_SOLVE

    def test_submit_failure(self):
        """異常系: タスク登録失敗"""
        page = MagicMock()
        submit_resp = MagicMock()
        submit_resp.json.return_value = {
            "status": 0, "request": "ERROR_ZERO_BALANCE",
        }
        with patch("utils.captcha_solver._get_api_key", return_value="KEY"), \
             patch("utils.captcha_solver.requests.post", return_value=submit_resp):
            result = solve_captcha(
                page, "http://x.com",
                {"type": "recaptcha_v2", "sitekey": "abc"},
            )
        assert result["solved"] is False
        assert result["error"] == "insufficient_balance"

    def test_boundary_injection_failure(self):
        """境界値: トークン取得後の注入失敗"""
        page = MagicMock()
        page.evaluate.side_effect = Exception("eval error")
        submit_resp = MagicMock()
        submit_resp.json.return_value = {"status": 1, "request": "id1"}
        poll_resp = MagicMock()
        poll_resp.json.return_value = {"status": 1, "request": "TOKEN"}

        with patch("utils.captcha_solver._get_api_key", return_value="KEY"), \
             patch("utils.captcha_solver.requests.post", return_value=submit_resp), \
             patch("utils.captcha_solver.requests.get", return_value=poll_resp), \
             patch("utils.captcha_solver.time.sleep"):
            result = solve_captcha(
                page, "http://x.com",
                {"type": "recaptcha_v2", "sitekey": "abc"},
            )

        assert result["solved"] is False
        assert result["error"] == "injection_failed"


def teardown_module():
    """テスト後にDBファイルを削除する"""
    import os
    try:
        os.unlink(str(db_module.DB_PATH))
    except OSError:
        pass
