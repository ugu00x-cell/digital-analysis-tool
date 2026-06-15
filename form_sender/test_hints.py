"""フィールド検出改善の動作確認"""
import sys
sys.path.insert(0, ".")
from utils.form_analyzer import classify_field, _get_field_hints
from bs4 import BeautifulSoup

# テーブルレイアウト（th/td）テスト
html = """
<table>
<tr>
  <th>お名前</th>
  <td><input name="entry_name" type="text"></td>
</tr>
<tr>
  <th>電話番号</th>
  <td><input name="tel1" type="text"></td>
</tr>
<tr>
  <th>郵便番号</th>
  <td><input name="zip_code" type="text"></td>
</tr>
<tr>
  <th>都道府県</th>
  <td><input name="area_pref" type="text"></td>
</tr>
<tr>
  <th>市区町村</th>
  <td><input name="area_city" type="text"></td>
</tr>
</table>
"""
soup = BeautifulSoup(html, "html.parser")
print("=== テーブルレイアウト ===")
for inp in soup.find_all("input"):
    hints = _get_field_hints(inp)
    ft = classify_field(inp)
    print(f"  name={inp.get('name')} -> ft={ft} (hints={hints[:80]})")

# dl/dt レイアウトテスト
html2 = """
<dl>
  <dt>会社名</dt>
  <dd><input name="comp" type="text"></dd>
  <dt>ご担当者名</dt>
  <dd><input name="person" type="text"></dd>
  <dt>メールアドレス</dt>
  <dd><input name="mail_addr" type="text"></dd>
</dl>
"""
soup2 = BeautifulSoup(html2, "html.parser")
print("\n=== dl/dt レイアウト ===")
for inp in soup2.find_all("input"):
    hints = _get_field_hints(inp)
    ft = classify_field(inp)
    print(f"  name={inp.get('name')} -> ft={ft} (hints={hints[:80]})")

# autocomplete テスト
html3 = """
<form>
  <input autocomplete="family-name" name="sei">
  <input autocomplete="given-name" name="mei">
  <input autocomplete="organization" name="corp">
  <input autocomplete="postal-code" name="zip">
  <input autocomplete="address-level1" name="ken">
  <input autocomplete="address-level2" name="shi">
</form>
"""
soup3 = BeautifulSoup(html3, "html.parser")
print("\n=== autocomplete ===")
for inp in soup3.find_all("input"):
    ft = classify_field(inp)
    print(f"  autocomplete={inp.get('autocomplete')} name={inp.get('name')} -> ft={ft}")

print("\n=== 完了 ===")
