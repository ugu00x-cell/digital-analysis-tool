"""
工程センサーデータ 異常検知ツール — エントリポイント

使い方:
    # サンプルデータで動かす（デフォルト）
    python main.py

    # 自分のCSVを指定する
    python main.py --input your_data.csv

    # 汚染率を調整する（デフォルト 0.05 = 全データの5%が異常と想定）
    python main.py --contamination 0.1

CSV フォーマット（--input を使う場合）:
    timestamp, temperature, pressure, vibration[, is_anomaly]
    is_anomaly カラムは任意（あれば精度評価もします）
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from data_generator import generate_sample_dataset
from detector import detect
from visualizer import plot_sensor_dashboard, plot_comparison_dashboard
from logger_config import get_logger

logger = get_logger(__name__)


def load_csv(path: str) -> pd.DataFrame:
    """CSV ファイルを読み込んで DataFrame を返す。

    Args:
        path: CSV ファイルのパス

    Returns:
        読み込んだ DataFrame

    Raises:
        SystemExit: ファイルが存在しないかカラムが不足している場合
    """
    p = Path(path)
    if not p.exists():
        logger.error(f'ファイルが見つかりません: {path}')
        sys.exit(1)

    df = pd.read_csv(p, parse_dates=['timestamp'])

    required = ['timestamp', 'temperature', 'pressure', 'vibration']
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.error(f'必須カラムが不足しています: {missing}')
        sys.exit(1)

    logger.info(f'CSV 読み込み完了: {path} ({len(df)}件)')
    return df


def print_summary(result) -> None:
    """検知結果のサマリーをコンソールに表示する。

    Args:
        result: DetectionResult オブジェクト
    """
    total = len(result.df)
    print('\n' + '=' * 55)
    print('  異常検知 結果サマリー')
    print('=' * 55)
    print(f'  総データ件数       : {total:,} 件')
    print(f'  Isolation Forest   : {result.if_anomaly_count:,} 件 ({result.if_anomaly_count / total * 100:.1f}%)')
    print(f'  3σ法               : {result.sigma_anomaly_count:,} 件 ({result.sigma_anomaly_count / total * 100:.1f}%)')
    print(f'  両手法が一致       : {result.both_anomaly_count:,} 件 ({result.both_anomaly_count / total * 100:.1f}%)')

    # 精度評価（ラベルがある場合のみ）
    if result.precision_if is not None:
        print()
        print('  ── 精度評価（正解ラベルあり）──')
        print(f'  Isolation Forest   Precision: {result.precision_if:.3f} / Recall: {result.recall_if:.3f}')
        print(f'  3σ法               Precision: {result.precision_sigma:.3f} / Recall: {result.recall_sigma:.3f}')

    print('=' * 55)
    print('  出力ファイル:')
    print('    output/sensor_timeseries.png  （センサー別時系列）')
    print('    output/comparison.png         （手法比較）')
    print('    output/result.csv             （予測結果CSV）')
    print('=' * 55 + '\n')


def parse_args() -> argparse.Namespace:
    """コマンドライン引数をパースする。

    Returns:
        パース済みの Namespace
    """
    parser = argparse.ArgumentParser(description='工程センサーデータ 異常検知ツール')
    parser.add_argument('--input',         type=str,   default=None,  help='入力CSVパス（省略でサンプルデータ使用）')
    parser.add_argument('--contamination', type=float, default=0.05,  help='Isolation Forest の汚染率（デフォルト: 0.05）')
    parser.add_argument('--output-dir',    type=str,   default='output', help='出力ディレクトリ（デフォルト: output）')
    return parser.parse_args()


def main() -> None:
    """メイン処理。データ読み込み → 異常検知 → 可視化 → 保存。"""
    # Windows の cp932 端末でも日本語を表示できるように utf-8 に変更
    sys.stdout.reconfigure(encoding='utf-8')
    args = parse_args()

    # ── データ準備 ──
    if args.input:
        df = load_csv(args.input)
    else:
        logger.info('サンプルデータを生成して使用します')
        df = generate_sample_dataset(
            n_samples=1440,
            output_path=f'{args.output_dir}/sample_input.csv'
        )

    # ── 異常検知 ──
    result = detect(df, contamination=args.contamination)

    # ── 可視化 ──
    plot_sensor_dashboard(
        result.df,
        result.thresholds,
        output_path=f'{args.output_dir}/sensor_timeseries.png'
    )
    plot_comparison_dashboard(
        result.df,
        precision_if=result.precision_if or 0,
        recall_if=result.recall_if or 0,
        precision_sigma=result.precision_sigma or 0,
        recall_sigma=result.recall_sigma or 0,
        output_path=f'{args.output_dir}/comparison.png'
    )

    # ── 結果CSV保存 ──
    out_csv = f'{args.output_dir}/result.csv'
    result.df.to_csv(out_csv, index=False)
    logger.info(f'結果CSV保存: {out_csv}')

    # ── サマリー表示 ──
    print_summary(result)


if __name__ == '__main__':
    main()
