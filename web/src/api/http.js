const TOKEN_KEY = 'platform2_token'
const ROLE_KEY = 'platform2_role'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

function roleFromToken(token) {
  try {
    const part = token.split('.')[1]
    if (!part) return ''
    const padded = part.replace(/-/g, '+').replace(/_/g, '/')
    const json = JSON.parse(atob(padded))
    return typeof json.role === 'string' ? json.role : ''
  } catch {
    return ''
  }
}

export function getRole() {
  const stored = localStorage.getItem(ROLE_KEY) || ''
  if (stored) return stored
  const fromToken = roleFromToken(getToken())
  if (fromToken) localStorage.setItem(ROLE_KEY, fromToken)
  return fromToken
}

export function setToken(token, role = '') {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
    if (role) localStorage.setItem(ROLE_KEY, role)
  } else {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(ROLE_KEY)
  }
}

export function isAdmin() {
  return getRole() === 'admin'
}

export async function api(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(path, { ...options, headers })
  if (!res.ok) {
    const text = await res.text()
    let detail = text || `HTTP ${res.status}`
    try {
      const body = JSON.parse(text)
      if (typeof body?.detail === 'string') detail = body.detail
      else if (Array.isArray(body?.detail)) {
        detail = body.detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
      }
    } catch {
      /* keep raw text */
    }
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}
