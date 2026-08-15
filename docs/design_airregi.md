# 開発設計書：airregi_daily_summary.sql 実装

**案件：** KUROCO / POS横断BigQuery KPI統合（Task 8）  
**作成日：** 2026-06-21  
**担当：** 竹中純也  
**対象ファイル：**
- `app/sql/airregi_daily_summary.sql`（新規作成）
- `app/clients/bigquery_client.py`（airregi メソッド追加）
- `app/background_tasks.py`（airregi 呼び出し追加）
- `app/etl.py`（エンドポイント追加）

---

## 背景・目的

Bionly（参考実装済み）・salon_answer・takara に続き、airregi のKPI日次集計SQLを作成する。  
出力スキーマは他POS と統一し、`pos_daily_summary.airregi` テーブルへ書き込む。

---

## airregi 固有のスキーマ課題（既調査）

| 課題 | 詳細 |
|------|------|
| スタイリスト名・顧客情報が別行に格納 | レシートヘッダー行と顧客行が分離している可能性。JOIN or PIVOT が必要 |
| 顧客情報が特定月のみ存在（6・7・9月はNULL） | NULLセーフな集計が必要。再来率KPIへの影響要確認 |
| クライアント確認待ち（2026-05-13時点） | NULLの扱い（除外 or ゼロ埋め）をクライアントと合意してから実装 |

---

## 対象KPI（全POS共通・出力スキーマ）

```sql
-- pos_daily_summary の出力カラム
date                          DATE
pos_name                      STRING   -- 'airregi'
active_customers              INT64    -- 180日以内来店顧客数
churned_customers             INT64    -- 180日離脱顧客数
new_customer_return_rate      FLOAT64  -- 新規顧客3ヶ月再来率（LEAD使用）
existing_customer_return_rate FLOAT64  -- 既存顧客3ヶ月再来率（LEAD使用）
avg_visit_interval_repeat     FLOAT64  -- 平均来店周期（LAG使用）
```

---

## Phase 設計

### Phase 0：前提確認（0.5〜1h）

**目的：** クライアント未確認事項を解消してから実装に入る。実装先行で後から仕様変更になるリスクを防ぐ。

**タスク：**
- [ ] クライアントに airregi の NULL 月（6・7・9月）の取り扱いを確認
  - 選択肢A：該当月を除外して集計
  - 選択肢B：顧客情報なしとしてゼロ埋め
  - 選択肢C：顧客IDをメールアドレス等の別カラムで代替
- [ ] airregi のスキーマドキュメント（DDL or サンプルCSV）を入手
- [ ] `pos_data.airregi` の実テーブル構造を BigQuery で確認

**完了条件：**
- NULL 月の扱い方針が文書化されている
- airregi テーブルの全カラム名・型・サンプル値が把握できている

---

### Phase 1：スキーマ解析・SQL設計（2〜3h）

**目的：** airregi 固有のデータ構造を理解し、他POSとの差異を吸収した集計ロジックを設計する。

**タスク：**
- [ ] `pos_data.airregi` のサンプルデータを SELECT して構造把握
  - 顧客行とレシート行の分離パターンを確認
  - NULL パターンの分布を確認（`COUNT(CASE WHEN customer_id IS NULL THEN 1 END)`）
- [ ] `bionly_daily_summary.sql` のロジックをコメント付きで読み解く（参照実装）
- [ ] airregi 向けのSQL設計メモを作成（擬似コード or フローチャート）
  - 顧客行をどう特定するか（行番号？カラム値？）
  - Window関数（LEAD/LAG）の適用範囲

**完了条件：**
- 設計メモが `docs/memo_airregi_schema.md` に存在する
- NULL 月を含む場合の集計挙動が定義されている

---

### Phase 2：SQL実装（3〜5h）

**目的：** `airregi_daily_summary.sql` を作成し、BigQuery で単体動作確認する。

**タスク：**
- [ ] `app/sql/airregi_daily_summary.sql` を新規作成
  - CTEで段階的に構築（生データ整形 → 顧客識別 → KPI集計）
  - NULL セーフな `SAFE_DIVIDE` / `COALESCE` を使用
- [ ] BigQuery コンソールで手動実行・出力確認
  - 他POS（salon_answer）の出力と行数・数値感を比較
  - NULL 月の扱いが設計通りか確認
- [ ] デバッグ・修正（想定：1〜2往復）

**完了条件：**
- BigQuery で実行エラーなし
- 出力カラムが共通スキーマと一致している
- NULL 月のレコードが設計通りに処理されている

---

### Phase 3：Pythonパイプライン組み込み（1〜2h）

**目的：** SQL を Python から呼べるようにし、日次バッチに組み込む。

**タスク：**
- [ ] `app/clients/bigquery_client.py` に `run_airregi_daily_summary()` メソッドを追加
  - 既存 `run_salon_answer_daily_summary()` を参考実装として踏襲
  - 型ヒント・docstring・logging を CLAUDE.md 基準で記述
- [ ] `app/background_tasks.py` に airregi の呼び出しを追加
- [ ] `app/etl.py` に `/etl/airregi` エンドポイントを追加（他POSと同じパターン）

**完了条件：**
- Python から SQL が呼び出せる
- ローカル環境でエラーなく実行完了する
- pytest テスト（正常系2・異常系2・境界値1）が PASSED

---

### Phase 4：検証・納品（1〜2h）

**目的：** 実データでの突合検証と、クライアントへの動作報告。

**タスク：**
- [ ] 実データで日次バッチを手動実行し、`pos_daily_summary.airregi` に書き込まれることを確認
- [ ] 他POS（salon_answer）の同日付レコードと数値感を比較・レビュー
- [ ] クライアントに動作報告（スクリーンショット or ログ添付）
- [ ] GitHub にコミット・プッシュ
- [ ] このドキュメントを「完了」に更新

**完了条件：**
- クライアントから動作確認の返答がある
- GitHub にコミット済み

---

## 工数見積もり（合計：7.5〜13h）

| Phase | 内容 | 工数 |
|-------|------|------|
| 0 | 前提確認 | 0.5〜1h |
| 1 | スキーマ解析・SQL設計 | 2〜3h |
| 2 | SQL実装 | 3〜5h |
| 3 | Python組み込み | 1〜2h |
| 4 | 検証・納品 | 1〜2h |

> 案件合意工数の残り（超過リスク考慮）と照らし合わせて、着手前に確認すること。

---

## CLAUDE.md チェックリスト（実装時の必須確認）

- [ ] 関数にdocstringあり
- [ ] 型ヒントあり
- [ ] エラーハンドリングあり
- [ ] `logger = logging.getLogger(__name__)` 形式のlogging使用
- [ ] 1関数50行以内
- [ ] 日本語コメントあり
- [ ] 1ファイル200行以内（超えそうなら分割提案）
- [ ] テスト：正常系2・異常系2・境界値1 がPASSED

---

## 備考・注意事項

- Phase 0 が完了するまで Phase 1 以降には着手しない（スキーマ不確実な状態での実装は手戻りリスク大）
- 1日あたりの作業は2〜3hまでに抑える（健康管理）
- 工数超過の兆候があれば、Phase 2 終了時点でクライアントに中間報告する
