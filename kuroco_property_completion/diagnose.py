"""診断スクリプト"""

import sys
print(f"✓ Python version: {sys.version}")
print(f"✓ Python executable: {sys.executable}")

# モジュールインポート確認
try:
    from services.bigquery_handler import BigQueryHandler
    print("✓ bigquery_handler imported successfully")
except ImportError as e:
    print(f"✗ Failed to import bigquery_handler: {e}")

try:
    from services.zipcode_fetcher import ZipcodeFetcher
    print("✓ zipcode_fetcher imported successfully")
except ImportError as e:
    print(f"✗ Failed to import zipcode_fetcher: {e}")

try:
    from services.suumo_scraper import SuumoScraper
    print("✓ suumo_scraper imported successfully")
except ImportError as e:
    print(f"✗ Failed to import suumo_scraper: {e}")

try:
    from services.master_mapper import MasterMapper
    print("✓ master_mapper imported successfully")
except ImportError as e:
    print(f"✗ Failed to import master_mapper: {e}")

try:
    from services.land_rights_completer import LandRightsCompleter
    print("✓ land_rights_completer imported successfully")
except ImportError as e:
    print(f"✗ Failed to import land_rights_completer: {e}")

try:
    from utils.text_matcher import TextMatcher
    print("✓ text_matcher imported successfully")
except ImportError as e:
    print(f"✗ Failed to import text_matcher: {e}")

print("\n✓ All modules checked. Attempting to run main.py...")

try:
    from main import PropertyCompletionManager
    print("✓ PropertyCompletionManager imported successfully")

    # 実行テスト
    print("\nInitializing PropertyCompletionManager...")
    manager = PropertyCompletionManager()
    print("✓ Manager initialized successfully")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
