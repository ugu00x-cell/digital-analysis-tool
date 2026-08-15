/**
 * M5Stack CoreS3 - 振動データ収集（ベアリング異常検知用）
 *
 * 動作:
 *   1. 起動 → IDLE画面（SD・IMU初期化）
 *   2. 画面タッチ → 500Hzで振動記録開始
 *   3. 画面タッチ → 記録停止、CSV保存完了
 *   4. 再タッチ → 新しいファイルで再度記録可能
 *
 * CSV形式: timestamp_us,ax,ay,az
 *   → analyze_vibration.py と互換
 */

#include <M5Unified.h>
#include <SD.h>
#include <SPI.h>
#include <SPIFFS.h>

// ── 定数 ─────────────────────────────────────────────────────
static const int SCR_W = 320;
static const int SCR_H = 240;

// サンプリング設定（analyze_vibration.py のFS=500に合わせる）
static const int SAMPLE_RATE_HZ  = 500;
static const int SAMPLE_INTERVAL = 1000000 / SAMPLE_RATE_HZ;  // 2000us
static const int BUF_SIZE        = 100;   // バッファサイズ（100サンプルで書き込み）
static const int DISPLAY_INTERVAL = 500;  // 画面更新間隔(ms)

// 色定義
static const uint16_t C_BG    = TFT_BLACK;
static const uint16_t C_TXT   = TFT_WHITE;
static const uint16_t C_CYAN  = 0xB7FF;
static const uint16_t C_GREEN = TFT_GREEN;
static const uint16_t C_RED   = TFT_RED;
static const uint16_t C_GRAY  = 0x7BEF;

// ── 状態管理 ─────────────────────────────────────────────────
enum AppState { ST_IDLE, ST_REC, ST_STOPPED };
static AppState appState = ST_IDLE;

// ── データバッファ ───────────────────────────────────────────
struct Sample {
    unsigned long ts_us;  // タイムスタンプ（us）
    float ax, ay, az;     // 加速度（g）
};
static Sample buf[BUF_SIZE];
static int bufIdx = 0;

// ── 記録管理 ─────────────────────────────────────────────────
static File csvFile;
static bool sdAvailable    = false;  // SD使用可能フラグ
static bool spiffsAvailable = false; // SPIFFS使用可能フラグ
static char fileName[40];
static unsigned long recStartUs   = 0;  // 記録開始時刻(us)
static unsigned long nextSampleUs = 0;  // 次のサンプル時刻(us)
static unsigned long totalSamples = 0;  // 合計サンプル数
static unsigned long lastDispMs   = 0;  // 最終画面更新時刻(ms)
static float rmsAz = 0.0f;             // リアルタイムRMS

// ── SDカード初期化 ───────────────────────────────────────────

/**
 * SDカードを初期化する
 */
static bool initSD() {
    Serial.println("[INFO] SD初期化開始...");

    // M5UnifiedからSDピン番号を取得
    int sclk = M5.getPin(m5::pin_name_t::sd_spi_sclk);
    int mosi = M5.getPin(m5::pin_name_t::sd_spi_mosi);
    int miso = M5.getPin(m5::pin_name_t::sd_spi_miso);
    int cs   = M5.getPin(m5::pin_name_t::sd_spi_cs);

    if (cs == 255 || sclk == 255) {
        Serial.println("[WARN] SDピン未定義");
        return false;
    }

    SPI.begin(sclk, miso, mosi, cs);
    if (!SD.begin(cs, SPI, 25000000)) {
        Serial.println("[WARN] SD.begin失敗");
        return false;
    }

    // 実際に書き込みテストして本当にSDが使えるか確認
    File test = SD.open("/_test.tmp", FILE_WRITE);
    if (!test) {
        Serial.println("[WARN] SD書き込みテスト失敗（誤検出）");
        SD.end();
        return false;
    }
    test.println("test");
    test.close();
    SD.remove("/_test.tmp");

    uint64_t total = SD.totalBytes() / (1024 * 1024);
    Serial.printf("[INFO] SD OK: %lluMB\n", total);
    return true;
}

// ── バッファ書き込み ─────────────────────────────────────────

/**
 * バッファ内のデータをSDに書き込む
 */
static void flushBuffer() {
    if (bufIdx == 0) return;

    if (sdAvailable && csvFile) {
        for (int i = 0; i < bufIdx; i++) {
            csvFile.printf("%lu,%.4f,%.4f,%.4f\n",
                           buf[i].ts_us,
                           buf[i].ax, buf[i].ay, buf[i].az);
        }
        csvFile.flush();
    }
    bufIdx = 0;
}

// ── ファイル名生成 ───────────────────────────────────────────

/**
 * 日時ベースのファイル名を生成する（RTCから取得）
 */
static void generateFileName() {
    auto dt = M5.Rtc.getDateTime();
    snprintf(fileName, sizeof(fileName),
             "/vibration_%04d%02d%02d_%02d%02d%02d.csv",
             dt.date.year, dt.date.month, dt.date.date,
             dt.time.hours, dt.time.minutes, dt.time.seconds);
}

// ── 画面描画 ─────────────────────────────────────────────────

/**
 * IDLE画面を表示する
 */
static void drawIdleScreen(bool sdOk) {
    M5.Display.fillScreen(C_BG);

    // タイトル
    M5.Display.setFont(&fonts::lgfxJapanGothicP_20);
    M5.Display.setTextColor(C_CYAN, C_BG);
    M5.Display.setTextDatum(middle_center);
    M5.Display.drawString("振動データ収集", SCR_W / 2, 30);

    // ステータス
    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(C_TXT, C_BG);
    M5.Display.drawString("IMU: BMI270 / 500Hz", SCR_W / 2, 70);

    if (sdOk) {
        M5.Display.setTextColor(C_GREEN, C_BG);
        M5.Display.drawString("保存先: SD", SCR_W / 2, 95);
    } else if (spiffsAvailable) {
        M5.Display.setTextColor(TFT_YELLOW, C_BG);
        M5.Display.drawString("保存先: SPIFFS (内蔵)", SCR_W / 2, 95);
    } else {
        M5.Display.setTextColor(C_RED, C_BG);
        M5.Display.drawString("保存先: なし", SCR_W / 2, 95);
    }

    // 操作ガイド
    M5.Display.setFont(&fonts::lgfxJapanGothicP_16);
    M5.Display.setTextColor(C_CYAN, C_BG);
    M5.Display.drawString("タッチで記録開始", SCR_W / 2, 160);

    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(C_GRAY, C_BG);
    M5.Display.drawString("analyze_vibration.py 互換CSV",
                           SCR_W / 2, 200);
    M5.Display.setTextDatum(top_left);
}

/**
 * 記録中画面を更新する（定期呼び出し）
 */
static void updateRecScreen() {
    float elapsedSec = (float)totalSamples / SAMPLE_RATE_HZ;

    M5.Display.fillScreen(C_BG);

    // ヘッダ
    M5.Display.setFont(&fonts::lgfxJapanGothicP_16);
    M5.Display.setTextColor(C_RED, C_BG);
    M5.Display.setTextDatum(middle_center);
    M5.Display.drawString("● REC", SCR_W / 2, 20);

    // 情報表示
    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(C_TXT, C_BG);
    M5.Display.setTextDatum(top_left);

    M5.Display.setCursor(20, 50);
    M5.Display.printf("Samples: %lu", totalSamples);

    M5.Display.setCursor(20, 75);
    M5.Display.printf("Time:    %.1f sec", elapsedSec);

    M5.Display.setCursor(20, 100);
    const char* storage = sdAvailable ? "SD" : (spiffsAvailable ? "SPIFFS" : "NONE");
    M5.Display.printf("Rate:    %d Hz  [%s]", SAMPLE_RATE_HZ, storage);

    // RMSメーター
    M5.Display.setCursor(20, 130);
    M5.Display.printf("RMS(az): %.4f g", rmsAz);

    // RMSバー表示（0〜2g スケール）
    int barW = (int)(rmsAz / 2.0f * 200);
    if (barW > 200) barW = 200;
    M5.Display.fillRect(20, 155, barW, 12, C_GREEN);
    M5.Display.drawRect(20, 155, 200, 12, C_GRAY);

    // ファイル名
    M5.Display.setFont(nullptr);
    M5.Display.setTextSize(1);
    M5.Display.setTextColor(C_GRAY, C_BG);
    M5.Display.setCursor(20, 180);
    M5.Display.print(fileName);

    // 操作ガイド
    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(C_CYAN, C_BG);
    M5.Display.setTextDatum(middle_center);
    M5.Display.drawString("タッチで記録停止", SCR_W / 2, 220);
    M5.Display.setTextDatum(top_left);
}

/**
 * 記録停止画面を表示する
 */
static void drawStoppedScreen() {
    float elapsedSec = (float)totalSamples / SAMPLE_RATE_HZ;

    M5.Display.fillScreen(C_BG);

    // 完了
    M5.Display.setFont(&fonts::lgfxJapanGothicP_20);
    M5.Display.setTextColor(C_GREEN, C_BG);
    M5.Display.setTextDatum(middle_center);
    M5.Display.drawString("保存完了！", SCR_W / 2, 30);

    // 結果
    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(C_TXT, C_BG);
    M5.Display.setTextDatum(top_left);

    M5.Display.setCursor(20, 65);
    M5.Display.printf("File: %s", fileName);

    M5.Display.setCursor(20, 90);
    M5.Display.printf("Samples: %lu", totalSamples);

    M5.Display.setCursor(20, 115);
    M5.Display.printf("Duration: %.1f sec", elapsedSec);

    M5.Display.setCursor(20, 140);
    M5.Display.printf("Size: %.1f KB",
                       (float)(totalSamples * 30) / 1024.0f);

    // 保存先情報
    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(C_GRAY, C_BG);
    M5.Display.setTextDatum(middle_center);
    if (sdAvailable) {
        M5.Display.drawString("SDをPCに移して解析", SCR_W / 2, 175);
    } else {
        M5.Display.drawString("USB接続でSPIFFS取得", SCR_W / 2, 175);
    }

    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(C_CYAN, C_BG);
    M5.Display.drawString("タッチで新規記録", SCR_W / 2, 225);
    M5.Display.setTextDatum(top_left);
}

// ── 記録制御 ─────────────────────────────────────────────────

/**
 * 記録を開始する
 */
static void startRecording() {
    generateFileName();

    // SD → SPIFFS の優先順位でファイルを開く
    if (sdAvailable) {
        csvFile = SD.open(fileName, FILE_WRITE);
        if (!csvFile) sdAvailable = false;
    }
    if (!sdAvailable && spiffsAvailable) {
        // SPIFFSはファイル名31文字制限があるので短縮
        snprintf(fileName, sizeof(fileName), "/vib_%lu.csv", millis() / 1000);
        csvFile = SPIFFS.open(fileName, FILE_WRITE);
    }
    if (csvFile) {
        csvFile.println("timestamp_us,ax,ay,az");
    }

    totalSamples = 0;
    bufIdx = 0;
    rmsAz = 0.0f;
    recStartUs = micros();
    nextSampleUs = recStartUs;
    lastDispMs = millis();
    appState = ST_REC;

    Serial.printf("[INFO] 記録開始: %s\n", fileName);
    updateRecScreen();
}

/**
 * 記録を停止する
 */
static void stopRecording() {
    // 残りバッファを書き込み
    flushBuffer();
    if (sdAvailable && csvFile) {
        csvFile.close();
    }

    appState = ST_STOPPED;
    Serial.printf("[INFO] 記録停止: %lu samples (%.1f sec)\n",
                  totalSamples,
                  (float)totalSamples / SAMPLE_RATE_HZ);
    drawStoppedScreen();
}

// ── setup ────────────────────────────────────────────────────

void setup() {
    auto cfg = M5.config();
    M5.begin(cfg);

    Serial.begin(115200);
    delay(500);  // USB CDC安定待ち
    Serial.println("=== 振動データ収集 (CoreS3) ===");

    // 起動診断画面
    M5.Display.fillScreen(C_BG);
    M5.Display.setFont(&fonts::lgfxJapanGothicP_16);
    M5.Display.setTextColor(C_CYAN, C_BG);
    M5.Display.setTextDatum(top_left);
    M5.Display.setCursor(10, 10);
    M5.Display.println("== 起動診断 ==");

    // IMU確認
    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    bool imuOk = M5.Imu.isEnabled();
    M5.Display.setCursor(10, 40);
    if (imuOk) {
        M5.Display.setTextColor(C_GREEN, C_BG);
        auto imuType = M5.Imu.getType();
        const char* imuName = "unknown";
        if (imuType == m5::imu_bmi270) imuName = "BMI270";
        else if (imuType == m5::imu_mpu6886) imuName = "MPU6886";
        M5.Display.printf("IMU: OK (%s)", imuName);
        // M5.Imu.update() を呼んでからデータ取得
        M5.Imu.update();
        auto data = M5.Imu.getImuData();
        M5.Display.setCursor(10, 60);
        M5.Display.setTextColor(C_TXT, C_BG);
        M5.Display.printf("ax=%.3f ay=%.3f az=%.3f",
                          data.accel.x, data.accel.y, data.accel.z);
    } else {
        M5.Display.setTextColor(C_RED, C_BG);
        M5.Display.println("IMU: NG");
    }

    // SD確認
    bool sdOk = initSD();
    sdAvailable = sdOk;
    M5.Display.setCursor(10, 85);
    if (sdOk) {
        M5.Display.setTextColor(C_GREEN, C_BG);
        uint64_t total = SD.totalBytes() / (1024 * 1024);
        M5.Display.printf("SD: OK (%lluMB)", total);
    } else {
        M5.Display.setTextColor(TFT_YELLOW, C_BG);
        M5.Display.println("SD: 未検出");
    }

    // SPIFFS確認
    spiffsAvailable = SPIFFS.begin(true);
    M5.Display.setCursor(10, 105);
    if (spiffsAvailable) {
        size_t total = SPIFFS.totalBytes() / 1024;
        size_t used  = SPIFFS.usedBytes() / 1024;
        M5.Display.setTextColor(C_GREEN, C_BG);
        M5.Display.printf("SPIFFS: OK (%dKB/%dKB)", used, total);
    } else {
        M5.Display.setTextColor(C_RED, C_BG);
        M5.Display.println("SPIFFS: NG");
    }

    // タッチ確認
    M5.Display.setCursor(10, 130);
    M5.Display.setTextColor(C_TXT, C_BG);
    M5.Display.println("Touch: waiting...");

    // 5秒間タッチ待ちテスト
    bool touchOk = false;
    for (int i = 0; i < 250; i++) {
        M5.update();
        if (M5.Touch.getCount() > 0) {
            auto t = M5.Touch.getDetail(0);
            M5.Display.fillRect(10, 130, 300, 20, C_BG);
            M5.Display.setCursor(10, 130);
            M5.Display.setTextColor(C_GREEN, C_BG);
            M5.Display.printf("Touch: OK (x=%d y=%d)", t.x, t.y);
            touchOk = true;
            delay(500);
            break;
        }
        delay(20);
    }
    if (!touchOk) {
        M5.Display.fillRect(10, 110, 300, 20, C_BG);
        M5.Display.setCursor(10, 110);
        M5.Display.setTextColor(TFT_YELLOW, C_BG);
        M5.Display.println("Touch: タイムアウト(5秒)");
    }

    // 2秒待ってからIDLE画面へ
    M5.Display.setCursor(10, 165);
    M5.Display.setTextColor(C_GRAY, C_BG);
    M5.Display.println("2秒後にメイン画面へ...");
    delay(2000);

    // IDLE画面表示
    drawIdleScreen(sdOk);
    // タッチ状態をクリア（診断中のタッチが残らないように）
    delay(500);
    for (int i = 0; i < 10; i++) { M5.update(); delay(20); }
    appState = ST_IDLE;
}

// ── loop ─────────────────────────────────────────────────────

void loop() {
    M5.update();

    switch (appState) {
    case ST_IDLE: {
        // タッチ状態を画面右下にリアルタイム表示
        int tc = M5.Touch.getCount();
        M5.Display.fillRect(200, 220, 120, 20, C_BG);
        M5.Display.setFont(nullptr);
        M5.Display.setTextSize(1);
        M5.Display.setTextColor(C_GRAY, C_BG);
        M5.Display.setCursor(200, 222);
        if (tc > 0) {
            auto tp = M5.Touch.getDetail(0);
            M5.Display.printf("T:%d,%d", tp.x, tp.y);
        } else {
            M5.Display.print("T:---");
        }

        // タッチ → 記録開始（指を離した瞬間に発動）
        static bool wasTouching = false;
        bool touching = (tc > 0);
        if (wasTouching && !touching) {
            startRecording();
        }
        wasTouching = touching;
        delay(50);
        break;
    }

    case ST_REC: {
        // 500Hzサンプリング
        unsigned long now = micros();
        if (now >= nextSampleUs) {
            nextSampleUs += SAMPLE_INTERVAL;

            // IMUデータ取得
            M5.Imu.update();
            auto data = M5.Imu.getImuData();

            buf[bufIdx].ts_us = now - recStartUs;
            buf[bufIdx].ax = data.accel.x;
            buf[bufIdx].ay = data.accel.y;
            buf[bufIdx].az = data.accel.z;
            bufIdx++;
            totalSamples++;

            // RMS計算（直近バッファ）
            static float sumSq = 0.0f;
            static int   rmsN  = 0;
            sumSq += data.accel.z * data.accel.z;
            rmsN++;
            if (rmsN >= SAMPLE_RATE_HZ / 2) {
                // 0.5秒ごとにRMS更新
                rmsAz = sqrtf(sumSq / rmsN);
                sumSq = 0.0f;
                rmsN = 0;
            }

            // バッファフル → SD書き込み
            if (bufIdx >= BUF_SIZE) {
                flushBuffer();
            }
        }

        // 画面更新（500msごと）
        if (millis() - lastDispMs >= DISPLAY_INTERVAL) {
            lastDispMs = millis();
            updateRecScreen();
        }

        // タッチ → 記録停止（指を離した瞬間）
        {
            static bool wasT = false;
            bool t = (M5.Touch.getCount() > 0);
            if (wasT && !t) {
                stopRecording();
            }
            wasT = t;
        }
        break;
    }

    case ST_STOPPED: {
        // タッチ → IDLEに戻る（指を離した瞬間）
        static bool wasT2 = false;
        bool t2 = (M5.Touch.getCount() > 0);
        if (wasT2 && !t2) {
            drawIdleScreen(true);
            appState = ST_IDLE;
        }
        wasT2 = t2;
        delay(20);
        break;
    }
    }
}
