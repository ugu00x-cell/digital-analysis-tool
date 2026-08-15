/**
 * M5StickCPlus2 - WiFiテザリング接続確認
 *
 * 動作:
 *   1. 起動時にテザリングAPへWiFi接続
 *   2. 接続成功 → IP・RSSI を液晶に表示
 *   3. 接続失敗 → エラー表示、ボタンAでリトライ
 */

#include <M5StickCPlus2.h>
#include <WiFi.h>

// WiFi設定（各自のSSID/パスワードに置き換えてください）
static const char* WIFI_SSID = "YOUR_WIFI_SSID";
static const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";

// 画面サイズ（M5StickCPlus2: 135x240）
static const int SCR_W = 135;
static const int SCR_H = 240;

/**
 * WiFi接続を試みて結果を液晶に表示する
 */
static bool connectWiFi() {
    // 接続中画面
    StickCP2.Display.fillScreen(TFT_BLACK);
    StickCP2.Display.setTextColor(TFT_CYAN);
    StickCP2.Display.setTextSize(2);
    StickCP2.Display.setCursor(10, 20);
    StickCP2.Display.println("WiFi");
    StickCP2.Display.setTextSize(1);
    StickCP2.Display.setCursor(10, 50);
    StickCP2.Display.println(WIFI_SSID);
    StickCP2.Display.setCursor(10, 70);
    StickCP2.Display.setTextColor(TFT_WHITE);
    StickCP2.Display.print("Connecting");

    Serial.printf("[INFO] WiFi接続開始: %s\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    // 接続待ち（最大15秒）
    for (int i = 0; i < 30; i++) {
        if (WiFi.status() == WL_CONNECTED) break;
        delay(500);
        StickCP2.Display.print(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
        String ip = WiFi.localIP().toString();
        int rssi = WiFi.RSSI();
        Serial.printf("[INFO] 接続成功: %s (RSSI: %d)\n", ip.c_str(), rssi);

        // 成功画面
        StickCP2.Display.fillScreen(TFT_BLACK);
        StickCP2.Display.setTextColor(TFT_GREEN);
        StickCP2.Display.setTextSize(2);
        StickCP2.Display.setCursor(10, 20);
        StickCP2.Display.println("OK!");

        StickCP2.Display.setTextSize(1);
        StickCP2.Display.setTextColor(TFT_WHITE);
        StickCP2.Display.setCursor(10, 60);
        StickCP2.Display.println("SSID:");
        StickCP2.Display.setCursor(10, 75);
        StickCP2.Display.println(WIFI_SSID);

        StickCP2.Display.setCursor(10, 100);
        StickCP2.Display.println("IP:");
        StickCP2.Display.setCursor(10, 115);
        StickCP2.Display.setTextColor(TFT_CYAN);
        StickCP2.Display.println(ip);

        StickCP2.Display.setCursor(10, 145);
        StickCP2.Display.setTextColor(TFT_WHITE);
        StickCP2.Display.printf("RSSI: %d dBm", rssi);

        // 電波強度バー表示
        StickCP2.Display.setCursor(10, 170);
        StickCP2.Display.print("Signal: ");
        int bars = 0;
        if (rssi > -50) bars = 5;
        else if (rssi > -60) bars = 4;
        else if (rssi > -70) bars = 3;
        else if (rssi > -80) bars = 2;
        else bars = 1;
        for (int i = 0; i < bars; i++) {
            StickCP2.Display.fillRect(75 + i * 12, 180 - i * 6,
                                       8, 10 + i * 6, TFT_GREEN);
        }

        StickCP2.Display.setTextColor(TFT_DARKGREY);
        StickCP2.Display.setCursor(10, 220);
        StickCP2.Display.print("BtnA: refresh");
        return true;
    }

    // 失敗画面
    Serial.println("[ERROR] WiFi接続失敗");
    StickCP2.Display.fillScreen(TFT_BLACK);
    StickCP2.Display.setTextColor(TFT_RED);
    StickCP2.Display.setTextSize(2);
    StickCP2.Display.setCursor(10, 20);
    StickCP2.Display.println("FAIL");
    StickCP2.Display.setTextSize(1);
    StickCP2.Display.setTextColor(TFT_WHITE);
    StickCP2.Display.setCursor(10, 60);
    StickCP2.Display.println(WIFI_SSID);
    StickCP2.Display.setCursor(10, 90);
    StickCP2.Display.setTextColor(TFT_DARKGREY);
    StickCP2.Display.println("BtnA: retry");
    return false;
}

/**
 * setup - 初期化
 */
void setup() {
    auto cfg = M5.config();
    StickCP2.begin(cfg);

    Serial.println("=== WiFi Tethering Test ===");
    StickCP2.Display.setRotation(0);  // 縦向き
    connectWiFi();
}

/**
 * loop - メインループ
 */
void loop() {
    StickCP2.update();

    // ボタンA → リトライ/リフレッシュ
    if (StickCP2.BtnA.wasPressed()) {
        WiFi.disconnect();
        delay(500);
        connectWiFi();
    }

    delay(20);
}
