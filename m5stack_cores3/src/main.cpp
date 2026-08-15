/**
 * M5Stack CoreS3 - 甘雨チャットアシスタント
 *
 * タッチキーボード → Gemini API → 液晶応答表示
 *
 * 使い方:
 *   1. config.h のWiFi・APIキーを実際の値に変更
 *   2. pio run --target upload
 */

#include <M5Unified.h>
#include <WiFi.h>
#include "config.h"
#include "api_client.h"

// =====================================================
//  レイアウト定数
// =====================================================
static const int SCR_W  = 320;
static const int SCR_H  = 240;
static const int INP_H  = 34;    // 入力バー高さ
static const int KB_Y   = 36;    // キーボード開始Y
static const int K_W    = 30;    // キー幅
static const int K_H    = 28;    // キー高さ
static const int R_P    = 30;    // 行ピッチ（K_H + gap）
static const int PRV_Y  = 158;   // 前回応答エリアY

// 色定義
static const uint16_t C_BG   = TFT_BLACK;
static const uint16_t C_INP  = 0x18C3;   // 入力バー背景（暗い青灰）
static const uint16_t C_KEY  = 0x4A49;   // キー背景
static const uint16_t C_SP   = 0x6B6D;   // 特殊キー背景
static const uint16_t C_SEND = 0x07FF;   // 送信ボタン（シアン）
static const uint16_t C_TXT  = TFT_WHITE;
static const uint16_t C_CYAN = 0xB7FF;   // 甘雨カラー

// =====================================================
//  状態管理
// =====================================================
enum AppState { ST_WIFI, ST_IDLE, ST_SEND, ST_RESP };
static AppState appSt   = ST_WIFI;
static String   inp     = "";       // 入力テキスト
static String   prevReply = "";     // 最新の応答
static bool     caps    = false;    // 大文字モード
static int      kbPg    = 0;       // 0=abc, 1=123

// キー文字列（各行）
static const char* KL[] = {"qwertyuiop", "asdfghjkl", "zxcvbnm"};
static const char* KU[] = {"QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"};
static const char* KN[] = {"1234567890", "@#$%&-+=(", ".,;:!?/"};

// =====================================================
//  キー1個描画
// =====================================================
static void drawKey(int x, int y, int w, int h,
                    const char* label, uint16_t bg) {
    M5.Display.fillRoundRect(x, y, w, h, 3, bg);
    M5.Display.setFont(nullptr);
    M5.Display.setTextColor(C_TXT, bg);

    int n = strlen(label);
    if (n == 1) {
        // 1文字 → 大きめ表示
        M5.Display.setTextSize(2);
        M5.Display.setCursor(x + (w - 12) / 2, y + (h - 16) / 2);
    } else {
        // 複数文字 → 小さめ表示
        M5.Display.setTextSize(1);
        M5.Display.setCursor(x + (w - n * 6) / 2, y + (h - 8) / 2);
    }
    M5.Display.print(label);
}

// =====================================================
//  キーボード全体描画
// =====================================================
static void drawKeyboard() {
    M5.Display.fillRect(0, KB_Y, SCR_W, PRV_Y - KB_Y, C_BG);

    const char** K = (kbPg == 1) ? KN : (caps ? KU : KL);

    // Row 0: 10キー（フル幅）
    for (int i = 0; i < (int)strlen(K[0]); i++) {
        char c[2] = {K[0][i], 0};
        drawKey(i * 32 + 1, KB_Y, K_W, K_H, c, C_KEY);
    }

    // Row 1: 9キー（半キー分インデント）
    for (int i = 0; i < (int)strlen(K[1]); i++) {
        char c[2] = {K[1][i], 0};
        drawKey(16 + i * 32, KB_Y + R_P, K_W, K_H, c, C_KEY);
    }

    // Row 2: CAP + 7キー + DEL
    drawKey(0, KB_Y + R_P * 2, 44, K_H,
            caps ? "cap" : "CAP", C_SP);
    for (int i = 0; i < (int)strlen(K[2]); i++) {
        char c[2] = {K[2][i], 0};
        drawKey(48 + i * 32, KB_Y + R_P * 2, K_W, K_H, c, C_KEY);
    }
    drawKey(SCR_W - 48, KB_Y + R_P * 2, 47, K_H, "DEL", C_SP);

    // Row 3: モード切替 + スペース + 送信
    drawKey(0,          KB_Y + R_P * 3, 76,  K_H,
            kbPg == 0 ? "123" : "abc", C_SP);
    drawKey(79,         KB_Y + R_P * 3, 160, K_H, "SPACE", C_KEY);
    drawKey(SCR_W - 80, KB_Y + R_P * 3, 79,  K_H, "SEND",  C_SEND);
}

// =====================================================
//  入力バー描画
// =====================================================
static void drawInput() {
    M5.Display.fillRect(0, 0, SCR_W, INP_H, C_INP);
    M5.Display.setFont(nullptr);
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(C_TXT, C_INP);
    M5.Display.setCursor(6, 9);

    // 長い入力は末尾を表示
    String d = inp;
    int maxLen = (SCR_W - 24) / 12;  // 12px/文字
    if ((int)d.length() > maxLen) {
        d = d.substring(d.length() - maxLen);
    }
    M5.Display.print(d);

    // カーソル
    M5.Display.setTextColor(C_SEND, C_INP);
    M5.Display.print("_");
}

// =====================================================
//  前回応答プレビュー描画
// =====================================================
static void drawPreview() {
    M5.Display.fillRect(0, PRV_Y, SCR_W, SCR_H - PRV_Y, C_BG);

    if (prevReply.length() == 0) {
        // 初期メッセージ
        M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
        M5.Display.setTextColor(0x4A49, C_BG);
        M5.Display.setCursor(50, PRV_Y + 24);
        M5.Display.print("甘雨にメッセージを送ろう！");
        return;
    }

    // 前回の応答をプレビュー表示
    M5.Display.setFont(&fonts::lgfxJapanGothicP_12);
    M5.Display.setTextColor(C_CYAN, C_BG);
    M5.Display.setTextWrap(true);
    M5.Display.setClipRect(0, PRV_Y, SCR_W, SCR_H - PRV_Y);
    M5.Display.setCursor(4, PRV_Y + 4);
    M5.Display.print(prevReply);
    M5.Display.clearClipRect();
}

// =====================================================
//  IDLE画面（キーボード画面）全体描画
// =====================================================
static void drawIdleScreen() {
    M5.Display.fillScreen(C_BG);
    drawInput();
    drawKeyboard();
    drawPreview();
}

// =====================================================
//  応答全画面表示
// =====================================================
static void drawResponseScreen() {
    M5.Display.fillScreen(C_BG);

    // ヘッダー：送った内容を小さく表示
    M5.Display.setFont(nullptr);
    M5.Display.setTextSize(1);
    M5.Display.setTextColor(C_SEND, C_BG);
    M5.Display.setCursor(4, 4);
    M5.Display.print("You> ");
    M5.Display.setTextColor(0x7BEF, C_BG);
    String q = inp;
    if ((int)q.length() > 42) q = q.substring(0, 42) + "...";
    M5.Display.print(q);

    // 区切り線
    M5.Display.drawFastHLine(0, 16, SCR_W, 0x4208);

    // 応答テキスト（日本語フォント）
    M5.Display.setFont(&fonts::lgfxJapanGothicP_20);
    M5.Display.setTextColor(C_TXT, C_BG);
    M5.Display.setTextWrap(true);
    M5.Display.setCursor(8, 24);
    M5.Display.print(prevReply);

    // 戻るガイド
    M5.Display.setFont(nullptr);
    M5.Display.setTextSize(1);
    M5.Display.setTextColor(0x7BEF, C_BG);
    M5.Display.setCursor(SCR_W / 2 - 36, SCR_H - 14);
    M5.Display.print("Tap to back");
}

// =====================================================
//  タッチ処理（キーボード入力）
// =====================================================
static void handleTouch(int tx, int ty) {
    // キーボード領域外は無視
    if (ty < KB_Y || ty >= PRV_Y) return;

    int row = (ty - KB_Y) / R_P;
    if (row < 0 || row > 3) return;

    const char** K = (kbPg == 1) ? KN : (caps ? KU : KL);
    bool redrawKB = false;

    switch (row) {
    case 0: {
        // Row 0: 10キー
        int col = tx / 32;
        if (col >= 0 && col < (int)strlen(K[0])) inp += K[0][col];
        break;
    }
    case 1: {
        // Row 1: 9キー（インデント）
        int col = (tx - 16) / 32;
        if (col >= 0 && col < (int)strlen(K[1])) inp += K[1][col];
        break;
    }
    case 2:
        // Row 2: CAP / 文字キー / DEL
        if (tx < 46) {
            if (kbPg == 0) { caps = !caps; redrawKB = true; }
        } else if (tx >= SCR_W - 48) {
            if (inp.length() > 0) inp.remove(inp.length() - 1);
        } else {
            int col = (tx - 48) / 32;
            if (col >= 0 && col < (int)strlen(K[2])) inp += K[2][col];
        }
        break;
    case 3:
        // Row 3: モード / スペース / 送信
        if (tx < 78) {
            kbPg = 1 - kbPg;
            redrawKB = true;
        } else if (tx >= SCR_W - 80) {
            if (inp.length() > 0) appSt = ST_SEND;
            return;  // 送信は呼び出し元に任せる
        } else {
            inp += ' ';
        }
        break;
    }

    drawInput();
    if (redrawKB) drawKeyboard();
}

// =====================================================
//  WiFi接続
// =====================================================
static bool connectWiFi() {
    M5.Display.fillScreen(C_BG);
    M5.Display.setFont(nullptr);
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(C_TXT);
    M5.Display.setCursor(10, 80);
    M5.Display.printf("WiFi: %s", WIFI_SSID);
    M5.Display.setCursor(10, 110);
    M5.Display.print("Connecting");

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    for (int i = 0; i < 30; i++) {
        if (WiFi.status() == WL_CONNECTED) break;
        delay(500);
        M5.Display.print(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("WiFi OK: %s\n", WiFi.localIP().toString().c_str());
        M5.Display.setCursor(10, 140);
        M5.Display.setTextColor(TFT_GREEN);
        M5.Display.print("Connected!");
        delay(800);
        return true;
    }

    M5.Display.setCursor(10, 140);
    M5.Display.setTextColor(TFT_RED);
    M5.Display.print("Failed!");
    return false;
}

// =====================================================
//  setup
// =====================================================
void setup() {
    auto cfg = M5.config();
    M5.begin(cfg);
    Serial.println("=== Ganyu Chat Assistant (Gemini) ===");

    if (connectWiFi()) {
        appSt = ST_IDLE;
        drawIdleScreen();
    }
}

// =====================================================
//  loop
// =====================================================
void loop() {
    M5.update();

    switch (appSt) {
    case ST_IDLE:
        // タッチ検出 → キーボード処理
        if (M5.Touch.getCount() > 0) {
            auto t = M5.Touch.getDetail(0);
            if (t.wasPressed()) {
                handleTouch(t.x, t.y);
            }
        }
        break;

    case ST_SEND: {
        // 送信中アニメーション
        M5.Display.fillScreen(C_BG);
        M5.Display.setFont(&fonts::lgfxJapanGothicP_20);
        M5.Display.setTextColor(C_SEND, C_BG);
        M5.Display.setCursor(56, SCR_H / 2 - 10);
        M5.Display.print("甘雨が考え中...");

        // API呼び出し
        prevReply = askGemini(inp);

        // 応答画面表示（inpはまだ残っている）
        drawResponseScreen();
        inp = "";
        appSt = ST_RESP;
        break;
    }

    case ST_RESP:
        // タップで入力画面に戻る
        if (M5.Touch.getCount() > 0) {
            auto t = M5.Touch.getDetail(0);
            if (t.wasPressed()) {
                appSt = ST_IDLE;
                drawIdleScreen();
            }
        }
        break;

    default:
        break;
    }

    delay(20);
}
