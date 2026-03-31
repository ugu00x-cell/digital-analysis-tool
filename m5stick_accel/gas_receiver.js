/**
 * Google Apps Script - M5StickC Plus2 加速度データ受信
 *
 * セットアップ手順:
 *   1. Googleスプレッドシートを新規作成
 *   2. 「拡張機能」→「Apps Script」を開く
 *   3. このコードを貼り付けて保存
 *   4. 「デプロイ」→「新しいデプロイ」
 *      - 種類: ウェブアプリ
 *      - 実行するユーザー: 自分
 *      - アクセスできるユーザー: 全員
 *   5. デプロイURLをArduinoコードの GAS_URL に設定
 */

// シート名（必要に応じて変更）
const SHEET_NAME = "AccelData";

/**
 * POSTリクエストを受け取り、スプレッドシートに加速度データを記録する
 */
function doPost(e) {
  try {
    // JSONデータをパース
    const data = JSON.parse(e.postData.contents);
    const x = data.x;
    const y = data.y;
    const z = data.z;

    // スプレッドシートに書き込み
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(SHEET_NAME);

    // シートが無ければ作成してヘッダー追加
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow(["タイムスタンプ", "X (G)", "Y (G)", "Z (G)", "合成加速度 (G)"]);
    }

    // 合成加速度を計算
    const magnitude = Math.sqrt(x * x + y * y + z * z);

    // データ行を追加
    sheet.appendRow([
      new Date(),                   // タイムスタンプ
      Math.round(x * 10000) / 10000,  // X
      Math.round(y * 10000) / 10000,  // Y
      Math.round(z * 10000) / 10000,  // Z
      Math.round(magnitude * 10000) / 10000  // 合成加速度
    ]);

    // 成功レスポンス
    return ContentService
      .createTextOutput(JSON.stringify({ status: "ok" }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    // エラーレスポンス
    return ContentService
      .createTextOutput(JSON.stringify({ status: "error", message: error.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * GETリクエスト（動作確認用）
 * ブラウザでGAS URLにアクセスすると「動作中」と表示される
 */
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({
      status: "running",
      message: "M5StickC Plus2 Accel Receiver is ready"
    }))
    .setMimeType(ContentService.MimeType.JSON);
}
