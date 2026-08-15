/**
 * API クライアント - STT・Gemini・VOICEVOX連携
 */

#pragma once
#include <Arduino.h>

/**
 * Google Speech-to-Text: 音声データをテキストに変換する
 * @param audio 16bit PCM音声データ
 * @param samples サンプル数
 * @return 認識されたテキスト（失敗時は空文字列）
 */
String speechToText(const int16_t* audio, size_t samples);

/**
 * Gemini API: テキストから甘雨口調の応答を生成する
 * @param userText ユーザーの入力テキスト
 * @return 甘雨の応答テキスト（失敗時は空文字列）
 */
String askGemini(const String& userText);

/**
 * VOICEVOX API: テキストを音声(WAV)に変換する
 * @param text 読み上げるテキスト
 * @param wavSize 出力WAVデータのサイズ（出力パラメータ）
 * @return WAVデータへのポインタ（PSRAM確保、呼び出し側でfree）
 *         失敗時はnullptrを返す
 */
uint8_t* textToSpeech(const String& text, size_t* wavSize);
