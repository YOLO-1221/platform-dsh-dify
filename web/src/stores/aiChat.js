import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, getToken } from '@/api/http'

export const useAiChatStore = defineStore('aiChat', () => {
  const sessionId = ref(null)
  const messages = ref([])
  const events = ref([])
  const streaming = ref(false)
  let abortController = null

  async function ensureSession() {
    if (sessionId.value) return sessionId.value
    const data = await api('/api/v1/ai/chat/session', { method: 'POST', body: '{}' })
    sessionId.value = data.id
    return sessionId.value
  }

  async function send(text) {
    await ensureSession()
    messages.value.push({ role: 'user', content: text })
    streaming.value = true
    events.value = []
    abortController = new AbortController()

    const url = `/api/v1/ai/chat/stream?session_id=${encodeURIComponent(sessionId.value)}&q=${encodeURIComponent(text)}`
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${getToken()}` },
      signal: abortController.signal,
    })
    if (!res.ok || !res.body) {
      streaming.value = false
      throw new Error(`SSE failed: ${res.status}`)
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let answer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''
      for (const chunk of chunks) {
        const line = chunk.split('\n').find((l) => l.startsWith('data:'))
        if (!line) continue
        const payload = JSON.parse(line.slice(5).trim())
        events.value.push(payload)
        if (payload.event_type === 'answer') {
          answer = payload.content || answer
          if (payload.business_payload) {
            // consumers (situation/task modules) listen via returned payload
            messages.value.push({
              role: 'assistant',
              content: answer,
              business_payload: payload.business_payload,
            })
          }
        }
      }
    }

    if (answer && !messages.value.some((m) => m.role === 'assistant' && m.content === answer)) {
      messages.value.push({ role: 'assistant', content: answer })
    }
    streaming.value = false
    return { answer, events: events.value }
  }

  function stop() {
    abortController?.abort()
    streaming.value = false
  }

  function clear() {
    messages.value = []
    events.value = []
  }

  return { sessionId, messages, events, streaming, ensureSession, send, stop, clear }
})
