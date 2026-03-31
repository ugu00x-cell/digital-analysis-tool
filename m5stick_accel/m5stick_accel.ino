/**
 * M5StickC Plus2 - 3軸加速度データ → Googleスプレッドシート送信
 *
 * 構成:
 *   M5StickC Plus2 (ESP32 + IMU) → WiFi → GAS WebApp → Googleスプレッドシート
 *
 * ライブラリ（Arduino IDE で事前にインストール）:
 *   - M5StickCPlus2 (Board: M5StickC Plus2)
 *   - HTTPClient（ESP32標準）
 *
 * 使い方:
 *   1. WiFi_SSID / WiFi_PASS を自分の環境に書き換える
 *   2. GAS_URL を自分のGASデプロイURLに書き換える
 *   3. SEND_INTERVAL_MS で送信間隔を調整（デフォルト1秒）
 */

#include <M5StickCPlus2.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ─── 設定（自分の環境に合わせて書き換える） ─────────────
const char* WIFI_SSID       = "YOUR_WIFI_SSID";      // WiFi SSID
const char* WIFI_PASS       = "YOUR_WIFI_PASSWORD";   // WiFi パスワード
const char* GAS_URL         = "YOUR_GAS_DEPLOY_URL";  // GASのWebアプリURL
const unsigned long SEND_INTERVAL_MS = 1000;          // 送信間隔（ミリ秒）

// ─── グローバル変数 ─────────────────────────────────────
float accX = 0.0f;  // X軸加速度 (G)
float accY = 0.0f;  // Y軸加速度 (G)
float accZ = 0.0f;  // Z軸加速度 (G)
unsigned long lastSendTime = 0;
unsigned long sendCount = 0;
bool wifiConnected = false;

// ─── WiFi接続 ──────────────────────────────────────────
void connectWiFi() {
    M5.Lcd.fillScreen(BLACK);
    M5.Lcd.setCursor(0, 0);
    M5.Lcd.setTextSize(2);
    M5.Lcd.println("WiFi...");

    WiFi.begin(WIFI_SSID, WIFI_PASS);

    int retryCount = 0;
    while (WiFi.status() != WL_CONNECTED && retryCount < 20) {
        delay(500);
        M5.Lcd.print(".");
        retryCount++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        wifiConnected = true;
        M5.Lcd.fillScreen(BLACK);
        M5.Lcd.setCursor(0, 0);
        M5.Lcd.println("WiFi OK!");
        M5.Lcd.println(WiFi.localIP().toString());
        delay(1000);
    } else {
        M5.Lcd.fillScreen(RED);
        M5.Lcd.setCursor(0, 0);
        M5.Lcd.println("WiFi NG");
        M5.Lcd.println("Check SSID/PASS");
    }
}

// ─── IMUから加速度データを取得 ─────────────────────────
void readAccelData() {
    // M5StickC Plus2 内蔵IMU（BMI270）から取得
    auto imu = M5.Imu;
    float ax, ay, az;

    if (imu.getAccel(&ax, &ay, &az)) {
        accX = ax;
        accY = ay;
        accZ = az;
    }
}

// ─── Googleスプレッドシートにデータ送信 ────────────────
bool sendToGoogleSheets(float x, float y, float z) {
    if (WiFi.status() != WL_CONNECTED) {
        return false;
    }

    HTTPClient http;
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
    http.begin(GAS_URL);
    http.addHeader("Content-Type", "application/json");

    // JSON形式でデータを送信
    // {"x": 0.01, "y": -0.02, "z": 0.98}
    char jsonBuffer[128];
    snprintf(jsonBuffer, sizeof(jsonBuffer),
             "{\"x\":%.4f,\"y\":%.4f,\"z\":%.4f}",
             x, y, z);

    int httpCode = http.POST(jsonBuffer);
    http.end();

    // 200 or 302（GASはリダイレクトする）
    return (httpCode == 200 || httpCode == 302);
}

// ─── LCD表示を更新 ─────────────────────────────────────
void updateDisplay() {
    M5.Lcd.fillScreen(BLACK);
    M5.Lcd.setCursor(0, 0);
    M5.Lcd.setTextSize(2);

    // ヘッダー
    M5.Lcd.setTextColor(CYAN);
    M5.Lcd.println("Accel Monitor");
    M5.Lcd.println("-------------");

    // 加速度値の表示
    M5.Lcd.setTextColor(WHITE);
    M5.Lcd.printf("X: %+.3f G\n", accX);
    M5.Lcd.printf("Y: %+.3f G\n", accY);
    M5.Lcd.printf("Z: %+.3f G\n", accZ);

    M5.Lcd.println();

    // 送信状態
    M5.Lcd.setTextColor(GREEN);
    M5.Lcd.printf("Send: %lu\n", sendCount);

    // WiFi状態
    if (WiFi.status() == WL_CONNECTED) {
        M5.Lcd.setTextColor(GREEN);
        M5.Lcd.println("WiFi: OK");
    } else {
        M5.Lcd.setTextColor(RED);
        M5.Lcd.println("WiFi: NG");
    }
}

// ─── セットアップ ──────────────────────────────────────
void setup() {
    // M5StickC Plus2 初期化（LCD + IMU + シリアル）
    auto cfg = M5.config();
    StickCP2.begin(cfg);

    Serial.begin(115200);
    Serial.println("[INFO] M5StickC Plus2 Accel Monitor");

    // LCD初期設定
    M5.Lcd.setRotation(1);
    M5.Lcd.fillScreen(BLACK);
    M5.Lcd.setTextSize(2);

    // WiFi接続
    connectWiFi();

    // 初回タイミング設定
    lastSendTime = millis();
    Serial.println("[INFO] Setup complete");
}

// ─── メインループ ──────────────────────────────────────
void loop() {
    M5.update();

    // IMUから加速度データ取得
    readAccelData();

    // 送信間隔チェック
    unsigned long now = millis();
    if (now - lastSendTime >= SEND_INTERVAL_MS) {
        lastSendTime = now;

        // シリアルモニタにも出力
        Serial.printf("[DATA] X=%.4f, Y=%.4f, Z=%.4f\n", accX, accY, accZ);

        // Googleスプレッドシートに送信
        if (wifiConnected) {
            bool ok = sendToGoogleSheets(accX, accY, accZ);
            if (ok) {
                sendCount++;
                Serial.printf("[INFO] Sent #%lu OK\n", sendCount);
            } else {
                Serial.println("[WARN] Send failed");
                // WiFi再接続を試みる
                if (WiFi.status() != WL_CONNECTED) {
                    Serial.println("[INFO] Reconnecting WiFi...");
                    connectWiFi();
                }
            }
        }

        // LCD更新
        updateDisplay();
    }

    // ボタンA短押し：送信間隔をシリアルに表示
    if (M5.BtnA.wasPressed()) {
        Serial.printf("[INFO] Interval: %lu ms, Count: %lu\n",
                      SEND_INTERVAL_MS, sendCount);
    }

    delay(10);  // CPU負荷軽減
}
