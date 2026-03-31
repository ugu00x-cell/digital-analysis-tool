"""
工具データベース＋材料物性データ
エンドミル加工の工具マスタと材料別の推奨切削条件パラメータを定義する
"""

# ─── 材料物性データ ─────────────────────────────────────
# Vc_range: 推奨切削速度の範囲 [m/min]
# fz_range: 1刃あたり送り量の範囲 [mm/tooth]（工具径10mm基準）
# ap_ratio: 軸方向切込み量の工具径に対する比率
# ae_ratio: 径方向切込み量の工具径に対する比率
# hardness: 硬度 HB
# machinability: 被削性指数（アルミ=1.0基準）
# life_factor: 工具寿命補正係数（アルミ=1.0基準）
MATERIALS: dict[str, dict] = {
    "S45C（炭素鋼）": {
        "key": "S45C",
        "Vc_range": (80, 150),
        "fz_range": (0.05, 0.12),
        "ap_ratio": (0.5, 1.0),
        "ae_ratio": (0.3, 0.5),
        "hardness": 200,
        "machinability": 0.6,
        "life_factor": 0.7,
        "notes": [
            "切りくず処理に注意（連続切りくずが出やすい）",
            "クーラントは水溶性を推奨",
            "仕上げ面粗さを重視する場合はVcを高めに設定",
        ],
    },
    "SUS304（ステンレス）": {
        "key": "SUS304",
        "Vc_range": (50, 100),
        "fz_range": (0.04, 0.08),
        "ap_ratio": (0.3, 0.8),
        "ae_ratio": (0.2, 0.4),
        "hardness": 187,
        "machinability": 0.35,
        "life_factor": 0.4,
        "notes": [
            "加工硬化しやすいため、低速・大送りが基本",
            "工具の逃げ面摩耗に注意（溶着が発生しやすい）",
            "クーラントは高圧・大量供給を推奨",
            "ダウンカットを推奨（加工硬化層を避ける）",
        ],
    },
    "A5052（アルミ合金）": {
        "key": "A5052",
        "Vc_range": (200, 500),
        "fz_range": (0.08, 0.20),
        "ap_ratio": (0.5, 1.5),
        "ae_ratio": (0.3, 0.7),
        "hardness": 68,
        "machinability": 1.0,
        "life_factor": 1.0,
        "notes": [
            "構成刃先（BUE）に注意（切削速度を上げると抑制できる）",
            "切りくずの排出性を確保すること",
            "DLCコーティング工具が有効",
        ],
    },
}

# ─── 工具データベース（エンドミル） ────────────────────
# maker: メーカー名
# series: シリーズ名
# model: 型番
# diameters: 在庫径 [mm]
# flutes: 刃数
# coating: コーティング
# helix_angle: ねじれ角 [度]
# materials: 推奨材料キー（複数可）
# grade: 超硬グレード
# price_range: 参考価格帯 [円]
TOOL_DB: list[dict] = [
    # ─ S45C向け ─
    {
        "maker": "三菱マテリアル",
        "series": "VQ",
        "model": "VQ4MBR",
        "diameters": [3, 4, 5, 6, 8, 10, 12, 16, 20],
        "flutes": 4,
        "coating": "TiAlN",
        "helix_angle": 30,
        "materials": ["S45C", "SUS304"],
        "grade": "超硬 VP15TF",
        "price_range": (4500, 12000),
        "Vc_boost": 1.0,
        "life_base_min": 60,
    },
    {
        "maker": "OSG",
        "series": "AE-VMS",
        "model": "AE-VMS-4",
        "diameters": [2, 3, 4, 5, 6, 8, 10, 12, 16, 20],
        "flutes": 4,
        "coating": "WXL（多層コーティング）",
        "helix_angle": 35,
        "materials": ["S45C"],
        "grade": "超硬 WXL",
        "price_range": (3800, 10000),
        "Vc_boost": 1.1,
        "life_base_min": 70,
    },
    # ─ SUS304向け ─
    {
        "maker": "日立ツール",
        "series": "エポックSUS",
        "model": "EPSS4",
        "diameters": [3, 4, 5, 6, 8, 10, 12, 16],
        "flutes": 4,
        "coating": "TiSiN",
        "helix_angle": 38,
        "materials": ["SUS304"],
        "grade": "超硬 SUS専用",
        "price_range": (5500, 15000),
        "Vc_boost": 1.15,
        "life_base_min": 45,
    },
    {
        "maker": "サンドビック",
        "series": "CoroMill Plura",
        "model": "2P160-xxxx-NA",
        "diameters": [4, 6, 8, 10, 12, 16, 20],
        "flutes": 4,
        "coating": "GC1630",
        "helix_angle": 40,
        "materials": ["SUS304", "S45C"],
        "grade": "超硬 GC1630",
        "price_range": (8000, 25000),
        "Vc_boost": 1.2,
        "life_base_min": 55,
    },
    # ─ アルミ向け ─
    {
        "maker": "ユニオンツール",
        "series": "UDCLRS",
        "model": "UDCLRS-2",
        "diameters": [3, 4, 5, 6, 8, 10, 12, 16, 20],
        "flutes": 2,
        "coating": "DLC",
        "helix_angle": 45,
        "materials": ["A5052"],
        "grade": "超硬 DLC",
        "price_range": (4000, 11000),
        "Vc_boost": 1.3,
        "life_base_min": 90,
    },
    {
        "maker": "OSG",
        "series": "AE-LNSS",
        "model": "AE-LNSS-3",
        "diameters": [3, 4, 5, 6, 8, 10, 12, 16, 20],
        "flutes": 3,
        "coating": "ノンコート（ミラー仕上げ）",
        "helix_angle": 45,
        "materials": ["A5052"],
        "grade": "超硬 ミラー",
        "price_range": (3500, 9000),
        "Vc_boost": 1.0,
        "life_base_min": 80,
    },
    # ─ 汎用 ─
    {
        "maker": "三菱マテリアル",
        "series": "MS4MC",
        "model": "MS4MCD",
        "diameters": [3, 4, 5, 6, 8, 10, 12, 16, 20, 25],
        "flutes": 4,
        "coating": "TiAlN",
        "helix_angle": 30,
        "materials": ["S45C", "SUS304", "A5052"],
        "grade": "超硬 汎用",
        "price_range": (3000, 8000),
        "Vc_boost": 0.9,
        "life_base_min": 50,
    },
]
