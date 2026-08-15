/**
 * API クライアント実装
 *
 * Google STT / Gemini API / VOICEVOX の3つのAPIを呼び出す。
 * 大きな音声データはPSRAMに確保して処理する。
 */

#include "api_client.h"
#include "config.h"

#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include "mbedtls/base64.h"

// =====================
// Base64エンコード（PSRAM使用）
// =====================
static char* base64Encode(const uint8_t* data, size_t len, size_t* outLen) {
    // 出力サイズを計算
    size_t needed = 0;
    mbedtls_base64_encode(NULL, 0, &needed, data, len);

    // PSRAM上にバッファ確保
    char* buf = (char*)ps_malloc(needed + 1);
    if (!buf) return nullptr;

    mbedtls_base64_encode((uint8_t*)buf, needed, outLen, data, len);
    buf[*outLen] = '\0';
    return buf;
}

// =====================
// HTTPS POST（SSL証明書検証スキップ）
// =====================
static String httpsPost(const String& url, const String& body,
                        const char* authHeader, const char* authValue,
                        const char* extraHeader = nullptr,
                        const char* extraValue = nullptr) {
    WiFiClientSecure client;
    client.setInsecure();  // プロトタイプ用（本番では証明書を設定）

    HTTPClient http;
    http.begin(client, url);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(30000);  // 30秒タイムアウト
    if (authHeader) {
        http.addHeader(authHeader, authValue);
    }
    // 追加ヘッダー（Claude APIのanthropicバージョン等）
    if (extraHeader) {
        http.addHeader(extraHeader, extraValue);
    }

    int code = http.POST(body);
    String response = "";
    if (code == 200) {
        response = http.getString();
    } else {
        Serial.printf("HTTP error: %d\n", code);
        if (code > 0) Serial.println(http.getString());
    }
    http.end();
    return response;
}

// =====================
// HTTP POST（平文・VOICEVOX用）
// =====================
static String httpPost(const String& url, const String& body,
                       const String& contentType) {
    HTTPClient http;
    http.begin(url);
    http.addHeader("Content-Type", contentType);
    http.setTimeout(30000);

    int code = http.POST(body);
    String response = "";
    if (code == 200) {
        response = http.getString();
    } else {
        Serial.printf("HTTP error: %d\n", code);
    }
    http.end();
    return response;
}

// =====================
// Google Speech-to-Text
// =====================
String speechToText(const int16_t* audio, size_t samples) {
    Serial.println("[STT] 音声認識開始...");

    // PCMデータをBase64エンコード
    size_t audioBytes = samples * sizeof(int16_t);
    size_t b64Len = 0;
    char* b64 = base64Encode((const uint8_t*)audio, audioBytes, &b64Len);
    if (!b64) {
        Serial.println("[STT] Base64エンコード失敗（メモリ不足）");
        return "";
    }
    Serial.printf("[STT] Base64: %d bytes\n", b64Len);

    // JSONリクエスト構築（PSRAMのString使用）
    String json;
    json.reserve(b64Len + 256);
    json = "{\"config\":{\"encoding\":\"LINEAR16\","
           "\"sampleRateHertz\":16000,"
           "\"languageCode\":\"ja-JP\"},"
           "\"audio\":{\"content\":\"";
    json += b64;
    json += "\"}}";
    free(b64);

    // API呼び出し
    String url = String("https://speech.googleapis.com/v1/speech:recognize?key=")
                 + GOOGLE_API_KEY;
    String resp = httpsPost(url, json, nullptr, nullptr);
    json = "";  // メモリ解放

    if (resp.isEmpty()) return "";

    // レスポンス解析
    JsonDocument doc;
    if (deserializeJson(doc, resp)) {
        Serial.println("[STT] JSONパース失敗");
        return "";
    }

    String transcript = doc["results"][0]["alternatives"][0]["transcript"]
                        .as<String>();
    Serial.printf("[STT] 認識結果: %s\n", transcript.c_str());
    return transcript;
}

// =====================
// Gemini API
// =====================
String askGemini(const String& userText) {
    Serial.printf("[Gemini] 入力: %s\n", userText.c_str());

    // エンドポイントURL構築（APIキーはクエリパラメータ）
    String url = "https://generativelanguage.googleapis.com/v1beta/models/";
    url += GEMINI_MODEL;
    url += ":generateContent?key=";
    url += GEMINI_API_KEY;

    // JSONリクエスト構築
    JsonDocument doc;

    // システムプロンプト（甘雨の口調設定）
    JsonObject sysInst = doc["system_instruction"].to<JsonObject>();
    JsonArray sysParts = sysInst["parts"].to<JsonArray>();
    JsonObject sysPart = sysParts.add<JsonObject>();
    sysPart["text"] = GANYU_PROMPT;

    // ユーザーメッセージ
    JsonArray contents = doc["contents"].to<JsonArray>();
    JsonObject content = contents.add<JsonObject>();
    content["role"] = "user";
    JsonArray parts = content["parts"].to<JsonArray>();
    JsonObject part = parts.add<JsonObject>();
    part["text"] = userText;

    String json;
    serializeJson(doc, json);

    // API呼び出し（認証はURLパラメータなのでヘッダー不要）
    String resp = httpsPost(url, json, nullptr, nullptr);

    if (resp.isEmpty()) return "";

    // レスポンス解析: candidates[0].content.parts[0].text
    JsonDocument resDoc;
    if (deserializeJson(resDoc, resp)) {
        Serial.println("[Gemini] JSONパース失敗");
        return "";
    }

    String reply = resDoc["candidates"][0]["content"]["parts"]
                         [0]["text"].as<String>();
    Serial.printf("[Gemini] 応答: %s\n", reply.c_str());
    return reply;
}

// =====================
// VOICEVOX API（2段階: audio_query → synthesis）
// =====================
uint8_t* textToSpeech(const String& text, size_t* wavSize) {
    Serial.printf("[TTS] テキスト: %s\n", text.c_str());
    *wavSize = 0;

    // Step1: audio_query（テキスト→クエリJSON）
    String queryUrl = String(VOICEVOX_HOST) + "/audio_query?text="
                      + text + "&speaker=" + VOICEVOX_SPEAKER;
    String queryJson = httpPost(queryUrl, "", "application/json");
    if (queryJson.isEmpty()) {
        Serial.println("[TTS] audio_query失敗");
        return nullptr;
    }

    // Step2: synthesis（クエリJSON→WAV音声）
    String synthUrl = String(VOICEVOX_HOST) + "/synthesis?speaker="
                      + VOICEVOX_SPEAKER;

    HTTPClient http;
    http.begin(synthUrl);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(30000);

    int code = http.POST(queryJson);
    if (code != 200) {
        Serial.printf("[TTS] synthesis失敗: %d\n", code);
        http.end();
        return nullptr;
    }

    // WAVデータをPSRAMに読み込む
    int len = http.getSize();
    if (len <= 0) {
        Serial.println("[TTS] WAVサイズ不明");
        http.end();
        return nullptr;
    }

    uint8_t* wav = (uint8_t*)ps_malloc(len);
    if (!wav) {
        Serial.println("[TTS] PSRAMメモリ不足");
        http.end();
        return nullptr;
    }

    WiFiClient* stream = http.getStreamPtr();
    size_t read = 0;
    while (read < (size_t)len) {
        size_t available = stream->available();
        if (available) {
            size_t chunk = stream->readBytes(wav + read, available);
            read += chunk;
        }
        delay(1);
    }

    http.end();
    *wavSize = len;
    Serial.printf("[TTS] WAV取得完了: %d bytes\n", len);
    return wav;
}
