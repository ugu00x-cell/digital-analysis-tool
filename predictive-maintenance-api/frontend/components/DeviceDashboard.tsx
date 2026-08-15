'use client'

import { useEffect, useState } from 'react'
import { z } from 'zod'

// AnalyzerサービスのURL(ローカル開発用)
const API_BASE_URL = 'http://localhost:8002'
// ポーリング間隔(ms)
const POLL_INTERVAL_MS = 30000
// 入力デバウンス時間(ms) - 入力が止まってから確定するまでの待ち時間
const DEBOUNCE_MS = 500

// APIレスポンスのランタイム検証スキーマ(バックエンドの形式変更を実行時に検知する)
const analyzeResultSchema = z.object({
  device_id: z.string(),
  is_anomaly: z.boolean(),
  max_z_score: z.number(),
  mean_rms: z.number(),
  peak_frequency_hz: z.number(),
  envelope_peak_hz: z.number(),
  threshold: z.number(),
  sample_count: z.number(),
  analyzed_at: z.string(),
})

const deviceStatusSchema = z.object({
  device_id: z.string(),
  last_analysis: analyzeResultSchema.nullable(),
  data_count: z.number(),
  last_received: z.string().nullable(),
})

type DeviceStatus = z.infer<typeof deviceStatusSchema>

// レスポンスをJSONとして読み取り、失敗時はエラーメッセージを組み立てる共通処理
async function parseOrThrow<T>(res: Response, schema: z.ZodType<T>): Promise<T> {
  const body = await res.json().catch(() => null)

  if (!res.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body
      ? String((body as { detail: unknown }).detail)
      : `通信エラー: ${res.status}`
    throw new Error(detail)
  }

  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    throw new Error('APIレスポンスの形式が想定と異なります')
  }
  return parsed.data
}

export default function DeviceDashboard() {
  const [deviceId, setDeviceId] = useState('m5stick_01')
  const [debouncedDeviceId, setDebouncedDeviceId] = useState('m5stick_01')
  const [status, setStatus] = useState<DeviceStatus | null>(null)
  const [statusError, setStatusError] = useState('')
  const [analysisError, setAnalysisError] = useState('')
  const [statusLoading, setStatusLoading] = useState(false)
  const [analysisLoading, setAnalysisLoading] = useState(false)

  const trimmedDeviceId = debouncedDeviceId.trim()

  // デバイスの最新ステータスを取得する
  async function fetchStatus(id: string) {
    if (!id) return
    setStatusLoading(true)
    setStatusError('')
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/status/${id}`)
      setStatus(await parseOrThrow(res, deviceStatusSchema))
    } catch (e) {
      setStatusError(e instanceof Error ? e.message : '通信エラーが発生しました')
    } finally {
      setStatusLoading(false)
    }
  }

  // 蓄積データに対して異常検知解析を実行する
  async function runAnalysis() {
    if (!trimmedDeviceId) return
    setAnalysisLoading(true)
    setAnalysisError('')
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: trimmedDeviceId }),
      })
      const result = await parseOrThrow(res, analyzeResultSchema)
      // /analyzeのレスポンスをそのまま反映し、/statusへの再取得は行わない
      setStatus((prev) => ({
        device_id: trimmedDeviceId,
        last_analysis: result,
        data_count: prev?.data_count ?? result.sample_count,
        last_received: prev?.last_received ?? null,
      }))
    } catch (e) {
      setAnalysisError(e instanceof Error ? e.message : '通信エラーが発生しました')
    } finally {
      setAnalysisLoading(false)
    }
  }

  // 入力欄の生の値。DEBOUNCE_MS止まってからdebouncedDeviceIdへ反映する
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedDeviceId(deviceId), DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [deviceId])

  // デバイスID確定時（デバウンス後）は前のデバイスの結果を残さないようクリアする
  useEffect(() => {
    setStatus(null)
    setStatusError('')
    setAnalysisError('')
  }, [trimmedDeviceId])

  // デバイスID確定後に自動取得し、以後は一定間隔でポーリングする
  useEffect(() => {
    if (!trimmedDeviceId) return
    fetchStatus(trimmedDeviceId)
    const timer = setInterval(() => fetchStatus(trimmedDeviceId), POLL_INTERVAL_MS)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trimmedDeviceId])

  const analysis = status?.last_analysis

  return (
    <div className="w-full max-w-2xl rounded-xl bg-white p-10 shadow-sm">
      <h1 className="mb-2 text-2xl font-semibold text-emerald-800">
        📈 予知保全ダッシュボード
      </h1>
      <p className="mb-6 text-sm text-zinc-500">
        デバイスの振動データ解析結果を確認します（{POLL_INTERVAL_MS / 1000}秒ごとに自動更新）
      </p>

      <div className="flex gap-2">
        <input
          value={deviceId}
          onChange={(e) => setDeviceId(e.target.value)}
          placeholder="デバイスID（例：m5stick_01）"
          className="flex-1 rounded-lg border border-zinc-300 p-3 text-base focus:border-emerald-700 focus:outline-none"
        />
      </div>

      <div className="mt-4 flex gap-3">
        <button
          onClick={() => fetchStatus(trimmedDeviceId)}
          disabled={statusLoading || !trimmedDeviceId}
          className="flex-1 rounded-lg border border-emerald-800 py-3 text-emerald-800 transition-colors hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {statusLoading ? '取得中…' : 'ステータス取得'}
        </button>
        <button
          onClick={runAnalysis}
          disabled={analysisLoading || !trimmedDeviceId}
          className="flex-1 rounded-lg bg-emerald-800 py-3 text-white transition-colors hover:bg-emerald-900 disabled:cursor-not-allowed disabled:bg-zinc-400"
        >
          {analysisLoading ? '解析中…' : '解析実行'}
        </button>
      </div>

      {!trimmedDeviceId && (
        <div className="mt-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-700">
          デバイスIDを入力してください
        </div>
      )}
      {statusError && (
        <div className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-700">
          {statusError}
        </div>
      )}
      {analysisError && (
        <div className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-700">
          {analysisError}
        </div>
      )}

      {status && (
        <div className="mt-8 rounded-lg bg-zinc-50 p-5 text-sm">
          <div className="mb-4 flex items-center justify-between">
            <span className="font-medium">{status.device_id}</span>
            {analysis && (
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  analysis.is_anomaly
                    ? 'bg-red-100 text-red-700'
                    : 'bg-emerald-100 text-emerald-700'
                }`}
              >
                {analysis.is_anomaly ? '🔴 異常' : '🟢 正常'}
              </span>
            )}
          </div>

          <dl className="grid grid-cols-2 gap-y-2 text-zinc-700">
            <dt className="text-zinc-500">データ件数</dt>
            <dd>{status.data_count.toLocaleString()} 件</dd>

            <dt className="text-zinc-500">最終受信</dt>
            <dd>{status.last_received ?? '—'}</dd>

            {analysis && (
              <>
                <dt className="text-zinc-500">最大Zスコア</dt>
                <dd>
                  {analysis.max_z_score.toFixed(2)}（閾値 {analysis.threshold}）
                </dd>

                <dt className="text-zinc-500">RMS平均</dt>
                <dd>{analysis.mean_rms.toFixed(4)} g</dd>

                <dt className="text-zinc-500">ピーク周波数</dt>
                <dd>{analysis.peak_frequency_hz.toFixed(1)} Hz</dd>

                <dt className="text-zinc-500">エンベロープピーク</dt>
                <dd>{analysis.envelope_peak_hz.toFixed(1)} Hz</dd>
              </>
            )}
          </dl>
        </div>
      )}
    </div>
  )
}
