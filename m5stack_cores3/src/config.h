/**
 * 設定ファイル - WiFi・APIキー・音声パラメータ
 *
 * 使用前に YOUR_*** の部分を実際の値に書き換えてください。
 */

#pragma once

// =====================
// WiFi設定
// =====================
static const char* WIFI_SSID     = "TP-Link_38C7";
static const char* WIFI_PASSWORD = "71222615";

// =====================
// Google Speech-to-Text API
// =====================
// Google Cloud Console → APIキーを取得
// Speech-to-Text APIを有効化すること
static const char* GOOGLE_API_KEY = "YOUR_GOOGLE_API_KEY";

// =====================
// Gemini API (Google)
// =====================
// 無料枠: 15 RPM / 1500 RPD
static const char* GEMINI_API_KEY = "AIzaSyCxFd6oFvk0MUsdoyAyfL3W7wPATEhOjw8";
static const char* GEMINI_MODEL   = "gemini-2.0-flash";

// =====================
// VOICEVOX API
// =====================
// VOICEVOXサーバーのURL（PC・VPS等で起動しておく）
// Docker: docker run -p 50021:50021 voicevox/voicevox_engine
static const char* VOICEVOX_HOST   = "http://YOUR_VOICEVOX_SERVER:50021";
static const int   VOICEVOX_SPEAKER = 0;  // 0=四国めたん(ノーマル)

// =====================
// 音声設定
// =====================
static const int MIC_SAMPLE_RATE = 16000;  // 16kHz
static const int RECORD_SECONDS  = 4;      // 録音時間（秒）
static const int MAX_SAMPLES     = MIC_SAMPLE_RATE * RECORD_SECONDS;

// =====================
// 甘雨システムプロンプト
// =====================
static const char* GANYU_PROMPT =
    "あなたは原神のキャラクター「甘雨」です。\n"
    "丁寧な敬語で落ち着いた口調で話します。\n"
    "相手のことは「旅人さん」と呼びます。\n"
    "友人として親しみやすく応答してください。\n"
    "ツノには触れないでください。\n"
    "応答は2〜3文で簡潔にしてください。";
