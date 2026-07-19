'use client'

import { useState } from 'react'

// FlaskバックエンドのURL(ローカル開発用)
const API_BASE_URL = 'http://localhost:5000'

export default function IngredientForm() {
  const [ingredients, setIngredients] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // 食材を送信し、SSEストリームを逐次読み取って結果に反映する
  async function handleGenerate() {
    const trimmed = ingredients.trim()
    if (!trimmed) {
      setError('食材を入力してください')
      return
    }

    setLoading(true)
    setError('')
    setResult('')

    try {
      const formData = new FormData()
      formData.append('ingredients', trimmed)

      const response = await fetch(`${API_BASE_URL}/generate`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(`サーバーエラー: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('レスポンスの読み取りに失敗しました')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const text = line.slice(6)
            if (text === '[DONE]') continue
            setResult((prev) => prev + text)
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '通信エラーが発生しました')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-2xl rounded-xl bg-white p-10 shadow-sm">
      <h1 className="mb-2 text-2xl font-semibold text-emerald-800">
        🍳 冷蔵庫から献立を提案
      </h1>
      <p className="mb-6 text-sm text-zinc-500">
        今ある食材を入力すると、AIが献立を考えてくれます
      </p>

      <textarea
        value={ingredients}
        onChange={(e) => setIngredients(e.target.value)}
        placeholder="例：卵、玉ねぎ、にんじん、鶏肉、醤油、みりん"
        className="min-h-28 w-full rounded-lg border border-zinc-300 p-3 text-base focus:border-emerald-700 focus:outline-none"
      />

      <button
        onClick={handleGenerate}
        disabled={loading}
        className="mt-4 w-full rounded-lg bg-emerald-800 py-3 text-white transition-colors hover:bg-emerald-900 disabled:cursor-not-allowed disabled:bg-zinc-400"
      >
        {loading ? '考え中…' : '献立を考える'}
      </button>

      {error && (
        <div className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-8 whitespace-pre-wrap rounded-lg bg-emerald-50 p-5 text-sm leading-relaxed">
          {result}
        </div>
      )}
    </div>
  )
}
