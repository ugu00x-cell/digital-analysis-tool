#include <M5StickCPlus2.h>
#include <WiFi.h>
#include <HTTPClient.h>

// WiFi設定（自分のものに変更）
const char* ssid = "";
const char* password = "";

// GoogleスプレッドシートのURL
const char* GAS_URL = "https://script.google.com/macros/s/AKfycbyTdYNc2bcpfLktQGK2tqx6g1vLU0ikfuBw2D23F4LaBbbMZMd1QFmRspAZI-NithTCyw/exec";

void setup() {
  auto cfg = M5.config();
  StickCP2.begin(cfg);
  Serial.begin(115200);

  // WiFi接続
  WiFi.begin(ssid, password);
  Serial.print("WiFi接続中");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi接続完了！");
}

void loop() {
  StickCP2.Imu.update();
  auto imu = StickCP2.Imu.getImuData();

  float x = imu.accel.x;
  float y = imu.accel.y;
  float z = imu.accel.z;

  Serial.printf("X:%.3f Y:%.3f Z:%.3f\n", x, y, z);

  // スプレッドシートに送信
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(GAS_URL);
    http.addHeader("Content-Type", "application/json");

    String json = "{\"x\":" + String(x) +
                  ",\"y\":" + String(y) +
                  ",\"z\":" + String(z) + "}";

    int code = http.POST(json);
    Serial.println("送信結果: " + String(code));
    http.end();
  }

  delay(5000); // 5秒ごとに送信
}
