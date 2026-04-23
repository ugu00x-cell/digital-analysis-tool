"""合成データ100件を生成して data/defects_raw.csv に保存する。

- ラベル別にフレーズテンプレートを持ち、ランダムサンプリングで揺れを再現
- 固定seedで再現性を確保
- 2024年内のランダム日付、3つの製品カテゴリ、連番idを付与
"""
import csv
import logging
import random
from datetime import date, timedelta
from pathlib import Path

from labels import PRODUCT_CATEGORIES, label_keys

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

# 生成件数と再現性用seed
TOTAL_SAMPLES = 100
RANDOM_SEED = 42

# 出力先（このファイルから見て ../data/defects_raw.csv）
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "defects_raw.csv"

# ラベル別のフレーズテンプレート
# 同じ現象の揺れ（同義語・語尾違い・助詞違い）を意図的に混ぜている
PHRASES: dict[str, list[str]] = {
    "bearing_noise": [
        "異音がする", "ガタガタ音がする", "キーキー鳴る",
        "回転時に音が変", "振動が大きい", "カラカラ音が出る",
        "唸るような音がする", "運転中にゴリゴリ音",
    ],
    "thermal_displacement": [
        "朝一は寸法OKだが昼から外れる", "温度が上がると公差外れ",
        "加工後半で寸法がずれる", "暖気運転後は規格内",
        "運転時間とともに寸法変動", "連続運転で寸法ドリフト",
    ],
    "assembly_scratch": [
        "打痕あり", "傷が入っている", "組立時に擦り傷",
        "表面に凹みがある", "搬送時にぶつけた跡", "小キズが複数",
    ],
    "alignment_error": [
        "取り付け時にがたつく", "芯が出ない", "ボルトが締まらない",
        "位置ずれあり", "軸が振れる", "センタリング不可", "取付穴が合わない",
    ],
    "dimension_oversize": [
        "オーバーサイズ", "寸法が大きい", "上限公差外れ",
        "径が大きすぎる", "プラス側に外れている",
    ],
    "dimension_undersize": [
        "アンダー", "寸法が小さい", "下限公差外れ",
        "径が小さすぎる", "マイナス側に外れている",
    ],
    "surface_rust": [
        "錆が出ている", "塗装剥げ", "メッキ剥がれ",
        "表面が変色", "防錆不良", "赤錆発生",
    ],
    "motion_alarm": [
        "動きが重い", "原点復帰しない", "アラームが出る",
        "途中で止まる", "サーボエラー", "動作停止",
    ],
}


def random_date_in_2024(rng: random.Random) -> date:
    """2024年内のランダムな日付を返す。

    Args:
        rng: 乱数生成器

    Returns:
        2024-01-01 〜 2024-12-31 のいずれかの日付
    """
    start = date(2024, 1, 1)
    # 2024年はうるう年なので366日
    offset = rng.randrange(366)
    return start + timedelta(days=offset)


def build_samples(total: int, seed: int) -> list[dict]:
    """指定件数の合成データを生成する。

    各ラベルからできるだけ均等にサンプリングし、
    端数はランダムに追加ラベルを選んで埋める。

    Args:
        total: 生成件数
        seed: 乱数シード

    Returns:
        id/date/product_category/defect_description/true_label を持つ辞書のリスト
    """
    rng = random.Random(seed)
    labels = label_keys()
    # 各ラベルに何件割り当てるかを決める
    base = total // len(labels)
    remainder = total % len(labels)
    counts = {lbl: base for lbl in labels}
    # 端数はランダムなラベルに上乗せ
    for extra_label in rng.sample(labels, remainder):
        counts[extra_label] += 1

    samples: list[dict] = []
    for label, count in counts.items():
        for _ in range(count):
            samples.append({
                "defect_description": rng.choice(PHRASES[label]),
                "true_label": label,
            })

    # 全体をシャッフルしてからid/date/製品カテゴリを付与（時系列ランダム性のため）
    rng.shuffle(samples)
    for i, sample in enumerate(samples, start=1):
        sample["id"] = i
        sample["date"] = random_date_in_2024(rng).isoformat()
        sample["product_category"] = rng.choice(PRODUCT_CATEGORIES)

    return samples


def write_csv(samples: list[dict], output_path: Path) -> None:
    """生成したサンプルをCSVに書き出す。

    Args:
        samples: サンプルの辞書リスト
        output_path: 出力先パス

    Raises:
        OSError: 出力先のディレクトリ作成・書き込みに失敗した場合
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Windowsでの改行を防ぐため newline=""
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "date", "product_category", "defect_description", "true_label"],
        )
        writer.writeheader()
        writer.writerows(samples)


def main() -> None:
    """合成データを生成してCSVに保存する。"""
    logger.info("合成データ%d件の生成を開始", TOTAL_SAMPLES)
    samples = build_samples(TOTAL_SAMPLES, RANDOM_SEED)
    write_csv(samples, OUTPUT_PATH)
    logger.info("生成完了: %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()
