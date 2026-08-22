"""business_generator.py のユニットテスト。

pytestのtmp_pathで一時ディレクトリを使用し、ファイルI/Oをテストする。
"""

from pathlib import Path

import pytest

from ai_business_db import business_generator


@pytest.fixture
def temp_db_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """DB_DIRを一時ディレクトリに差し替えるフィクスチャ。"""
    temp_dir = tmp_path / "business_data"
    monkeypatch.setattr(business_generator, "DB_DIR", temp_dir)
    return temp_dir


def test_generate_mock_businesses() -> None:
    """正常系: ダミーのビジネス情報が期待通りに生成される。"""
    businesses = business_generator.generate_mock_businesses()

    assert len(businesses) == 5
    assert all("id" in b and "name" in b and "model" in b for b in businesses)
    assert businesses[0]["name"] == "AIWritingAssistant"
    assert businesses[4]["name"] == "CodeReviewGPT"


def test_generate_html_for_business() -> None:
    """正常系: ビジネス情報がHTML形式に正しく変換される。"""
    business = {
        "id": 1,
        "name": "TestBusiness",
        "model": "AIを使ったテスト用ビジネス",
        "source": "TestNews",
        "date": "2026-08-15",
    }

    html = business_generator.generate_html_for_business(business)

    assert "<!DOCTYPE html>" in html
    assert "TestBusiness" in html
    assert "AIを使ったテスト用ビジネス" in html
    assert "TestNews" in html
    assert "2026-08-15" in html


def test_save_business_html_creates_file(temp_db_dir: Path) -> None:
    """正常系: save_business_html()がファイルを作成する。"""
    business = {
        "id": 1,
        "name": "TestBusiness",
        "model": "Test",
        "source": "Test",
        "date": "2026-08-15",
    }

    file_path = business_generator.save_business_html(business)

    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "TestBusiness" in content


def test_generate_index_html() -> None:
    """正常系: インデックスHTMLが全ビジネスへのリンクを含む。"""
    businesses = business_generator.generate_mock_businesses()

    index_html = business_generator.generate_index_html(businesses)

    assert "<!DOCTYPE html>" in index_html
    assert "AIスモールビジネス情報データベース" in index_html
    assert "AIWritingAssistant" in index_html
    assert "CodeReviewGPT" in index_html
    assert f"({len(businesses)}件)" in index_html


def test_save_business_html_raises_oserror_on_invalid_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """異常系: ディレクトリ作成不可な場所を指定するとOSErrorを送出する。"""
    blocking_file = tmp_path / "blocked"
    blocking_file.write_text("dummy", encoding="utf-8")
    invalid_db_dir = blocking_file / "business_data"
    monkeypatch.setattr(business_generator, "DB_DIR", invalid_db_dir)

    business = {
        "id": 1,
        "name": "Test",
        "model": "Test",
        "source": "Test",
        "date": "2026-08-15",
    }

    with pytest.raises(OSError):
        business_generator.save_business_html(business)
