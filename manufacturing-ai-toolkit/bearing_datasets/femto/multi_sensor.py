"""
FEMTO/PRONOSTIA — マルチセンサー（振動＋温度）検証
振動だけでは捉えられない劣化予兆が温度データに現れるかを検証する

重要な制約:
- 訓練データ（Learning_set）には温度データがない
- テストデータ（Full_Test_Set）のBearing1_4〜1_7, 2_4〜2_6に温度あり
- このため「Bearing1_2の温度で予兆を見つける」は直接検証できない
- テストデータのベアリングで振動＋温度の相補性を検証する

注意: 全ての数値は「異常検出率（異常判定割合）」であり精度ではない
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from scipy.signal import hilbert
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 定数
DATA_DIR = Path(__file__).parent / "data"
REPO_DIR = DATA_DIR / "repo"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

SAMPLING_RATE = 25600
NORMAL_RATIO = 0.20
LATE_RATIO = 0.10

# 温度データがあるベアリング（Full_Test_Set）
TEMP_BEARINGS: dict[str, str] = {
    'Bearing1_4': 'Full_Test_Set',
    'Bearing1_5': 'Full_Test_Set',
    'Bearing1_6': 'Full_Test_Set',
    'Bearing1_7': 'Full_Test_Set',
    'Bearing2_4': 'Full_Test_Set',
    'Bearing2_5': 'Full_Test_Set',
    'Bearing2_6': 'Full_Test_Set',
}

# 振動のみの特徴量カラム
VIB_FEATURE_COLS = [
    'h_rms', 'h_kurtosis', 'h_crest_factor', 'h_envelope_rms',
]
# 温度特徴量カラム
TEMP_FEATURE_COLS = ['temp_mean', 'temp_std', 'temp_rate']
# 複合特徴量カラム
COMBINED_COLS = VIB_FEATURE_COLS + TEMP_FEATURE_COLS


def load_acc_snapshot(csv_path: Path) -> np.ndarray | None:
    """振動スナップショットを読み込む（6列、カンマまたはセミコロン区切り）"""
    try:
        # まずカンマ区切りで試行、1列ならセミコロン区切り
        data = pd.read_csv(csv_path, header=None).values
        if data.shape[1] < 6:
            data = pd.read_csv(csv_path, header=None, sep=';').values
        return data[:, 4:6].astype(float)  # 水平・垂直振動
    except Exception as e:
        logger.warning(f"振動読み込みスキップ: {csv_path.name} ({e})")
        return None


def load_temp_snapshot(csv_path: Path) -> float | None:
    """温度スナップショットを読み込む（セミコロン区切り5列）"""
    try:
        data = pd.read_csv(csv_path, header=None, sep=';').values
        temp_values = data[:, 4].astype(float)
        return float(np.mean(temp_values))
    except Exception as e:
        logger.warning(f"温度読み込みスキップ: {csv_path.name} ({e})")
        return None


def compute_vib_features(signal: np.ndarray) -> dict[str, float]:
    """振動信号から特徴量を抽出する"""
    rms = float(np.sqrt(np.mean(signal ** 2)))
    peak = float(np.max(np.abs(signal)))
    kurtosis = float(sp_stats.kurtosis(signal))
    crest_factor = float(peak / rms) if rms > 0 else 0.0
    envelope = np.abs(hilbert(signal))
    envelope_rms = float(np.sqrt(np.mean(envelope ** 2)))

    return {
        'h_rms': rms,
        'h_kurtosis': kurtosis,
        'h_crest_factor': crest_factor,
        'h_envelope_rms': envelope_rms,
    }


def extract_bearing_features(
    bearing_name: str,
    dataset: str,
) -> pd.DataFrame:
    """振動＋温度の特徴量を抽出する"""
    bearing_dir = REPO_DIR / dataset / bearing_name
    if not bearing_dir.exists():
        logger.error(f"ディレクトリなし: {bearing_dir}")
        return pd.DataFrame()

    acc_files = sorted(bearing_dir.glob("acc_*.csv"))
    temp_files = sorted(bearing_dir.glob("temp_*.csv"))

    logger.info(f"  {bearing_name}: acc={len(acc_files)}, temp={len(temp_files)}")

    # 温度のインデックスマップ（ファイル番号→温度値）
    temp_map: dict[str, float] = {}
    for tf in temp_files:
        val = load_temp_snapshot(tf)
        if val is not None:
            # temp_00001.csv → 00001
            idx_str = tf.stem.replace('temp_', '')
            temp_map[idx_str] = val

    records: list[dict] = []
    prev_temp = None
    for idx, acc_file in enumerate(acc_files):
        data = load_acc_snapshot(acc_file)
        if data is None:
            continue

        # 振動特徴量
        features = compute_vib_features(data[:, 0])
        features['snapshot_idx'] = idx

        # 温度特徴量（対応するインデックスがあれば）
        idx_str = acc_file.stem.replace('acc_', '')
        if idx_str in temp_map:
            temp_val = temp_map[idx_str]
            features['temp_mean'] = temp_val
            features['temp_std'] = 0.0  # スナップショット平均のため
            # 温度変化率（前回との差分）
            if prev_temp is not None:
                features['temp_rate'] = temp_val - prev_temp
            else:
                features['temp_rate'] = 0.0
            prev_temp = temp_val
        else:
            features['temp_mean'] = np.nan
            features['temp_std'] = np.nan
            features['temp_rate'] = np.nan

        records.append(features)

    return pd.DataFrame(records)


def plot_temp_vs_rms(
    df: pd.DataFrame,
    bearing_name: str,
) -> None:
    """振動RMSと温度の時系列を重ねてプロットする"""
    has_temp = df['temp_mean'].notna().any()
    if not has_temp:
        logger.info(f"  {bearing_name}: 温度データなし、スキップ")
        return

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    idx = df['snapshot_idx'].values
    life_pct = np.linspace(0, 100, len(df))

    # 上段: RMS
    axes[0].plot(life_pct, df['h_rms'].values, linewidth=0.5, color='#4CAF50')
    axes[0].set_ylabel('RMS (Horizontal)', fontsize=11)
    axes[0].set_title(f'{bearing_name} - Vibration RMS vs Temperature',
                     fontsize=14, fontweight='bold')
    axes[0].grid(True, alpha=0.3)

    # 中段: 温度
    temp_mask = df['temp_mean'].notna()
    axes[1].plot(life_pct[temp_mask], df.loc[temp_mask, 'temp_mean'].values,
                linewidth=1.0, color='#F44336')
    axes[1].set_ylabel('Temperature [°C]', fontsize=11)
    axes[1].grid(True, alpha=0.3)

    # 下段: 温度変化率
    rate_mask = df['temp_rate'].notna()
    axes[2].plot(life_pct[rate_mask], df.loc[rate_mask, 'temp_rate'].values,
                linewidth=0.5, color='#FF9800')
    axes[2].set_ylabel('Temp Rate [°C/step]', fontsize=11)
    axes[2].set_xlabel('Life Percentage [%]', fontsize=12)
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = OUTPUT_DIR / f"temp_vs_rms_{bearing_name}.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"  温度-RMS比較保存: {output_path.name}")


def run_anomaly_detection(
    df: pd.DataFrame,
    feature_cols: list[str],
    label: str,
) -> dict[str, float]:
    """IsolationForestで区間別の検出率を算出する"""
    # NaN行を除外
    valid = df.dropna(subset=feature_cols)
    if len(valid) < 10:
        logger.warning(f"  {label}: データ不足({len(valid)}行)")
        return {'normal_fa': np.nan, 'late_det': np.nan}

    X = valid[feature_cols].values
    n = len(X)
    n_train = max(1, int(n * NORMAL_RATIO))
    n_late = max(1, int(n * LATE_RATIO))

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200, contamination=0.05,
        random_state=42, n_jobs=-1,
    )
    model.fit(X_scaled[:n_train])

    preds = model.predict(X_scaled)
    anomaly = np.where(preds == -1, 1, 0)

    fa = float(np.mean(anomaly[:n_train]))
    det = float(np.mean(anomaly[-n_late:]))
    return {'normal_fa': fa, 'late_det': det}


def compare_sensor_modes(
    all_data: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """振動のみ / 温度のみ / 振動＋温度 を比較する"""
    records: list[dict] = []

    for name, df in sorted(all_data.items()):
        has_temp = df['temp_mean'].notna().any()
        n_temp = int(df['temp_mean'].notna().sum())

        # 振動のみ
        vib_result = run_anomaly_detection(df, VIB_FEATURE_COLS, f"{name}/vib")

        record = {
            'bearing': name,
            'n_snapshots': len(df),
            'n_temp': n_temp,
            'vib_fa': vib_result['normal_fa'],
            'vib_det': vib_result['late_det'],
        }

        if has_temp and n_temp > 20:
            # 温度のみ
            temp_result = run_anomaly_detection(df, TEMP_FEATURE_COLS, f"{name}/temp")
            record['temp_fa'] = temp_result['normal_fa']
            record['temp_det'] = temp_result['late_det']

            # 振動＋温度
            combined_result = run_anomaly_detection(df, COMBINED_COLS, f"{name}/combined")
            record['combined_fa'] = combined_result['normal_fa']
            record['combined_det'] = combined_result['late_det']
        else:
            record['temp_fa'] = np.nan
            record['temp_det'] = np.nan
            record['combined_fa'] = np.nan
            record['combined_det'] = np.nan

        records.append(record)

        logger.info(
            f"  {name}: "
            f"振動[誤報{vib_result['normal_fa']:.1%} 検出{vib_result['late_det']:.1%}] "
            f"温度[誤報{record.get('temp_fa', float('nan')):.1%} "
            f"検出{record.get('temp_det', float('nan')):.1%}] "
            f"複合[誤報{record.get('combined_fa', float('nan')):.1%} "
            f"検出{record.get('combined_det', float('nan')):.1%}]"
        )

    return pd.DataFrame(records)


def plot_sensor_comparison(results_df: pd.DataFrame) -> None:
    """振動のみ / 温度のみ / 複合 の検出率を棒グラフで比較する"""
    # 温度データがあるベアリングだけ抽出
    valid = results_df[results_df['temp_det'].notna()].copy()
    if valid.empty:
        logger.warning("温度データのあるベアリングがありません")
        return

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    names = valid['bearing'].values
    x = np.arange(len(names))
    width = 0.25

    # 左: 誤報率
    axes[0].bar(x - width, valid['vib_fa'].values, width,
               label='Vibration Only', color='#4CAF50', alpha=0.8)
    axes[0].bar(x, valid['temp_fa'].values, width,
               label='Temperature Only', color='#F44336', alpha=0.8)
    axes[0].bar(x + width, valid['combined_fa'].values, width,
               label='Vib + Temp', color='#2196F3', alpha=0.8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(names, fontsize=9, rotation=30, ha='right')
    axes[0].set_ylabel('False Alarm Rate (Normal 20%)', fontsize=11)
    axes[0].set_title('False Alarm Rate by Sensor Mode', fontsize=13, fontweight='bold')
    axes[0].legend(fontsize=9)
    axes[0].grid(True, alpha=0.3, axis='y')

    # 右: 末期検出率
    axes[1].bar(x - width, valid['vib_det'].values, width,
               label='Vibration Only', color='#4CAF50', alpha=0.8)
    axes[1].bar(x, valid['temp_det'].values, width,
               label='Temperature Only', color='#F44336', alpha=0.8)
    axes[1].bar(x + width, valid['combined_det'].values, width,
               label='Vib + Temp', color='#2196F3', alpha=0.8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(names, fontsize=9, rotation=30, ha='right')
    axes[1].set_ylabel('Late Detection Rate (Last 10%)', fontsize=11)
    axes[1].set_title('Late Detection Rate by Sensor Mode', fontsize=13, fontweight='bold')
    axes[1].legend(fontsize=9)
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].set_ylim(0, 1.15)

    fig.suptitle(
        'Multi-Sensor Anomaly Detection Comparison\n'
        '(Note: Detection rates, not accuracy)',
        fontsize=14, fontweight='bold', y=1.02
    )
    plt.tight_layout()
    output_path = OUTPUT_DIR / "multi_sensor_comparison.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"マルチセンサー比較保存: {output_path.name}")


def print_summary(results_df: pd.DataFrame) -> None:
    """結果サマリをログ出力する"""
    logger.info("=" * 70)
    logger.info("=== マルチセンサー検証サマリ ===")
    logger.info("※全て異常検出率（異常判定割合）。精度ではない。")
    logger.info("=" * 70)

    logger.info(f"{'Bearing':<14} {'振動誤報':>8} {'振動検出':>8} "
                f"{'温度誤報':>8} {'温度検出':>8} "
                f"{'複合誤報':>8} {'複合検出':>8}")
    logger.info("-" * 70)

    for _, row in results_df.iterrows():
        temp_fa = f"{row['temp_fa']:.1%}" if pd.notna(row['temp_fa']) else "N/A"
        temp_det = f"{row['temp_det']:.1%}" if pd.notna(row['temp_det']) else "N/A"
        comb_fa = f"{row['combined_fa']:.1%}" if pd.notna(row['combined_fa']) else "N/A"
        comb_det = f"{row['combined_det']:.1%}" if pd.notna(row['combined_det']) else "N/A"
        logger.info(
            f"{row['bearing']:<14} "
            f"{row['vib_fa']:>7.1%} {row['vib_det']:>7.1%} "
            f"{temp_fa:>7} {temp_det:>7} "
            f"{comb_fa:>7} {comb_det:>7}"
        )

    # 温度データの改善効果
    valid = results_df[results_df['combined_det'].notna()]
    if not valid.empty:
        logger.info("\n=== 温度追加による末期検出率の変化 ===")
        for _, row in valid.iterrows():
            diff = row['combined_det'] - row['vib_det']
            direction = "改善" if diff > 0.01 else "悪化" if diff < -0.01 else "同等"
            logger.info(
                f"  {row['bearing']}: "
                f"振動のみ={row['vib_det']:.1%} → 複合={row['combined_det']:.1%} "
                f"({direction}: {diff:+.1%})"
            )


def main() -> None:
    """マルチセンサー検証の全工程を実行する"""
    logger.info("=== マルチセンサー（振動＋温度）検証開始 ===")
    logger.info("※以下の数値は全て「異常検出率（異常判定割合）」であり精度ではありません")
    logger.info("")
    logger.info("【重要な制約】")
    logger.info("  訓練データ（Learning_set: Bearing1_1〜3_2）には温度データがない")
    logger.info("  テストデータ（Full_Test_Set: Bearing1_4〜2_6の一部）に温度データがある")
    logger.info("  → Bearing1_2の温度予兆は直接検証できない")
    logger.info("")

    # テストデータの温度ありベアリングの特徴量を抽出
    all_data: dict[str, pd.DataFrame] = {}
    for name, dataset in TEMP_BEARINGS.items():
        logger.info(f"特徴量抽出: {name}")
        df = extract_bearing_features(name, dataset)
        if not df.empty:
            all_data[name] = df

    if not all_data:
        logger.error("データなし。download_data.pyを先に実行してください。")
        return

    # 温度 vs RMS の可視化
    logger.info("=== 温度-RMS可視化 ===")
    for name, df in sorted(all_data.items()):
        plot_temp_vs_rms(df, name)

    # 振動のみ / 温度のみ / 複合 の異常検知比較
    logger.info("=== センサーモード別異常検知 ===")
    results_df = compare_sensor_modes(all_data)

    # 比較グラフ
    plot_sensor_comparison(results_df)

    # サマリ出力
    print_summary(results_df)

    logger.info("=== マルチセンサー検証完了 ===")


if __name__ == "__main__":
    main()
