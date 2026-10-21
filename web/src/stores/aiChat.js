import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, getToken } from '@/api/http'

export const useAiChatStore = defineStore('aiChat', () => {
  const sessionId = ref(null)
  const messages = ref([])
  const events = ref([])
  const streaming = ref(false)
  const lastBusinessPayload = ref(null)
  let abortController = null

  async function ensureSession() {
    if (sessionId.value) return sessionId.value
    const data = await api('/api/v1/ai/chat/session', { method: 'POST', body: '{}' })
    sessionId.value = data.id
    return sessionId.value
  }

  /**
   * @param {string} text
   * @param {{ taskId?: string|null, done?: string[] }} [opts]
   */
  async function send(text, opts = {}) {
    const taskId = typeof opts === 'string' || opts == null ? opts : opts.taskId
    const done = Array.isArray(opts?.done) ? opts.done : []

    await ensureSession()
    messages.value.push({ role: 'user', content: text })
    streaming.value = true
    events.value = []
    lastBusinessPayload.value = null
    abortController = new AbortController()

    const params = new URLSearchParams({
      session_id: sessionId.value,
      q: text,
    })
    if (taskId) params.set('task_id', taskId)
    if (done.length) params.set('done', done.join(','))
    const url = `/api/v1/ai/chat/stream?${params.toString()}`
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
      const { done: streamDone, value } = await reader.read()
      if (streamDone) break
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
            lastBusinessPayload.value = payload.business_payload
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
    return { answer, events: events.value, business_payload: lastBusinessPayload.value }
  }

  function stop() {
    abortController?.abort()
    streaming.value = false
  }

  function clear() {
    messages.value = []
    events.value = []
    lastBusinessPayload.value = null
  }

  return {
    sessionId,
    messages,
    events,
    streaming,
    lastBusinessPayload,
    ensureSession,
    send,
    stop,
    clear,
  }
})
