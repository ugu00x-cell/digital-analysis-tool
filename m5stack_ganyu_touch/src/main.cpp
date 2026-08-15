/**
 * M5Stack CoreS3 - 甘雨タッチデモ + WiFiテザリング接続確認
 *
 * 動作:
 *   1. 起動時にWiFi（テザリング）接続
 *   2. 接続成功 → 甘雨画像を表示
 *   3. 画面タッチ → 「はい、甘雨です」+ IPアドレス表示
 *   4. 3秒後に元の画像に戻る
 */

#include <M5Unified.h>
#include <SPIFFS.h>
#include <WiFi.h>

// WiFi設定（テザリング）
static const char* WIFI_SSID = "AQUOS zero2_2998";
static const char* WIFI_PASS = "pgy2525c";

// 画面サイズ
static const int SCR_W = 320;
static const int SCR_H = 240;

// 画像パス
static const char* IMG_PATH = "/ganyu.bmp";

// 画像バッファ（PSRAM上に確保）
static uint8_t* bmpBuf = nullptr;
static size_t   bmpSize = 0;

// 状態管理
enum AppState {
    ST_WIFI,    // WiFi接続中
    ST_IMAGE,   // 画像表示中（タッチ待ち）
    ST_TEXT,    // テキスト表示中（タイマー待ち）
};

static AppState appState = ST_WIFI;
static unsigned long textStartMs = 0;
static const unsigned long TEXT_DURATION = 3000;

// 色定義
static const uint16_t C_BG   = TFT_BLACK;
static const uint16_t C_TXT  = TFT_WHITE;
static const uint16_t C_CYAN = 0xB7FF;  // 甘雨カラー（水色）

/**
 * SPIFFSからBMPファイルをPSRAMに読み込む
 */
static bool loadBmpToBuffer() {
    File f = SPIFFS.open(IMG_PATH, "r");
    if (!f) {
        Serial.println("[WARN] /ganyu.bmp を開けません");
        return false;
    }

    bmpSize = f.size();
    bmpBuf = (uint8_t*)ps_malloc(bmpSize);
    if (!bmpBuf) {
        bmpBuf = (uint8_t*)malloc(bmpSize);
    }
    if (!bmpBuf) {
        Serial.println("[ERROR] メモリ確保失敗");
        f.close();
        return false;
    }

    f.read(bmpBuf, bmpSize);
    f.close();
    Serial.printf("[INFO] BMP読み込み完了: %d bytes\n", bmpSize);
    return true;
}

/**
 * WiFi接続画面を表示して接続を試みる
 */
static bool connectWiFi() {
    M5.Display.fillScreen(C_BG);
    M5.Display.setFont(&fonts::lgfxJapanGothicP_20);
    M5.Display.setTextColor(C_CYAN, C_BG);
    M5.Display.setTextDatum(middle_center);
    M5.Display.drawString("WiFi接続中...", SCR_W / 2, 60);

    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(0x7BEF, C_BG);
    M5.Display.drawString(WIFI_SSID, SCR_W / 2, 100);
    M5.Display.setTextDatum(top_left);

    Serial.printf("[INFO] WiFi接続開始: %s\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    // 接続待ち（最大15秒）
    int dots = 0;
    for (int i = 0; i < 30; i++) {
        if (WiFi.status() == WL_CONNECTED) break;
        delay(500);

        // ドットアニメーション
        dots++;
        M5.Display.setFont(nullptr);
        M5.Display.setTextSize(2);
        M5.Display.setTextColor(C_TXT, C_BG);
        M5.Display.setCursor(100, 140);
        String d = "";
        for (int j = 0; j < (dots % 4); j++) d += ".";
        d += "   ";  // 前回表示のクリア用
        M5.Display.print(d);
    }

    if (WiFi.status() == WL_CONNECTED) {
        String ip = WiFi.localIP().toString();
        Serial.printf("[INFO] WiFi接続成功: %s\n", ip.c_str());

        // 接続成功表示
        M5.Display.fillScreen(C_BG);
        M5.Display.setFont(&fonts::lgfxJapanGothicP_20);
        M5.Display.setTextColor(TFT_GREEN, C_BG);
        M5.Display.setTextDatum(middle_center);
        M5.Display.drawString("接続成功！", SCR_W / 2, 80);

        M5.Display.setFont(&fonts::lgfxJapanGothicP_16);
        M5.Display.setTextColor(C_TXT, C_BG);
        M5.Display.drawString(("IP: " + ip).c_str(), SCR_W / 2, 120);

        M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
        M5.Display.setTextColor(0x7BEF, C_BG);
        M5.Display.drawString(("RSSI: " + String(WiFi.RSSI()) + " dBm").c_str(),
                              SCR_W / 2, 160);
        M5.Display.setTextDatum(top_left);

        delay(2000);
        return true;
    }

    Serial.println("[ERROR] WiFi接続失敗");
    M5.Display.fillScreen(C_BG);
    M5.Display.setFont(&fonts::lgfxJapanGothicP_20);
    M5.Display.setTextColor(TFT_RED, C_BG);
    M5.Display.setTextDatum(middle_center);
    M5.Display.drawString("接続失敗...", SCR_W / 2, 100);
    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(0x7BEF, C_BG);
    M5.Display.drawString("タッチでリトライ", SCR_W / 2, 140);
    M5.Display.setTextDatum(top_left);
    return false;
}

/**
 * 甘雨画像を液晶に表示する
 */
static void showGanyuImage() {
    if (bmpBuf && bmpSize > 0) {
        M5.Display.drawBmp(bmpBuf, bmpSize, 0, 0);
        Serial.println("[INFO] 甘雨画像を表示しました");
        return;
    }

    // フォールバック表示
    M5.Display.fillScreen(C_BG);
    M5.Display.setFont(&fonts::lgfxJapanGothicP_20);
    M5.Display.setTextColor(C_CYAN, C_BG);
    M5.Display.setTextDatum(middle_center);
    M5.Display.drawString("甘雨", SCR_W / 2, SCR_H / 2 - 20);
    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(0x7BEF, C_BG);
    M5.Display.drawString("(画像: /ganyu.bmp 未検出)", SCR_W / 2, SCR_H / 2 + 20);
    M5.Display.setTextDatum(top_left);
}

/**
 * タッチ時のテキスト表示（IPアドレス付き）
 */
static void showResponseText() {
    M5.Display.fillScreen(C_BG);

    // メインテキスト
    M5.Display.setFont(&fonts::lgfxJapanGothicP_28);
    M5.Display.setTextColor(C_CYAN, C_BG);
    M5.Display.setTextDatum(middle_center);
    M5.Display.drawString("はい、甘雨です", SCR_W / 2, SCR_H / 2 - 30);

    // WiFiステータス
    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    if (WiFi.status() == WL_CONNECTED) {
        M5.Display.setTextColor(TFT_GREEN, C_BG);
        String info = "WiFi OK  IP: " + WiFi.localIP().toString();
        M5.Display.drawString(info.c_str(), SCR_W / 2, SCR_H / 2 + 10);

        M5.Display.setTextColor(0x7BEF, C_BG);
        String rssi = "RSSI: " + String(WiFi.RSSI()) + " dBm";
        M5.Display.drawString(rssi.c_str(), SCR_W / 2, SCR_H / 2 + 30);
    } else {
        M5.Display.setTextColor(TFT_RED, C_BG);
        M5.Display.drawString("WiFi 未接続", SCR_W / 2, SCR_H / 2 + 10);
    }

    // 下部ガイド
    M5.Display.setTextColor(0x4A49, C_BG);
    M5.Display.drawString("3秒後に戻ります...", SCR_W / 2, SCR_H - 20);
    M5.Display.setTextDatum(top_left);

    Serial.println("[INFO] タッチ検出 → テキスト表示");
}

/**
 * setup - 初期化
 */
void setup() {
    auto cfg = M5.config();
    M5.begin(cfg);

    Serial.println("=== 甘雨タッチデモ + WiFiテザリング ===");

    // SPIFFS初期化
    if (!SPIFFS.begin(true)) {
        Serial.println("[ERROR] SPIFFS初期化失敗");
        M5.Display.fillScreen(TFT_RED);
        M5.Display.setFont(nullptr);
        M5.Display.setTextSize(2);
        M5.Display.setTextColor(C_TXT);
        M5.Display.setCursor(10, 100);
        M5.Display.print("SPIFFS ERROR");
        return;
    }

    // BMP読み込み
    loadBmpToBuffer();

    // WiFi接続
    if (connectWiFi()) {
        showGanyuImage();
        appState = ST_IMAGE;
    }
    // 失敗時はST_WIFIのまま（タッチでリトライ）
}

/**
 * loop - メインループ
 */
void loop() {
    M5.update();

    switch (appState) {
    case ST_WIFI:
        // タッチでリトライ
        if (M5.Touch.getCount() > 0) {
            auto t = M5.Touch.getDetail(0);
            if (t.wasPressed()) {
                if (connectWiFi()) {
                    showGanyuImage();
                    appState = ST_IMAGE;
                }
            }
        }
        break;

    case ST_IMAGE:
        // タッチ → テキスト表示
        if (M5.Touch.getCount() > 0) {
            auto t = M5.Touch.getDetail(0);
            if (t.wasPressed()) {
                showResponseText();
                textStartMs = millis();
                appState = ST_TEXT;
            }
        }
        break;

    case ST_TEXT:
        // 3秒後 → 画像に戻る
        if (millis() - textStartMs >= TEXT_DURATION) {
            showGanyuImage();
            appState = ST_IMAGE;
        }
        break;
    }

    delay(20);
}
