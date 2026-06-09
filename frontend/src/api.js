const API_BASE = '/api'

function getAuthHeaders() {
  const token = localStorage.getItem('token')
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}

async function parseResponse(response) {
  if (!response.ok) {
    let message = 'Request failed'
    try {
      const data = await response.json()
      message = data.message || data.error || message
    } catch (e) {
      try {
        const text = await response.text()
        message = text || message
      } catch (err) {
        // ignore
      }
    }
    throw new Error(message)
  }
  return response.json()
}

export async function login(username, password) {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  })
  const data = await parseResponse(response)
  if (data.token) {
    localStorage.setItem('token', data.token)
  }
  return data
}

export async function register(username, email, password, fullName) {
  const response = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password, fullName })
  })
  const data = await parseResponse(response)
  if (data.token) {
    localStorage.setItem('token', data.token)
  }
  return data
}

export async function getMe() {
  const response = await fetch(`${API_BASE}/auth/me`, {
    method: 'GET',
    headers: getAuthHeaders()
  })
  return parseResponse(response)
}

export function logout() {
  localStorage.removeItem('token')
}

export async function searchSongs(query) {
  const endpoint = query
    ? `${API_BASE}/songs?q=${encodeURIComponent(query)}`
    : `${API_BASE}/popular?limit=12`

  const data = await parseResponse(await fetch(endpoint))
  return Array.isArray(data) ? data : []
}

export async function getRecommendations(trackId, topN = 10) {
  const data = await parseResponse(
    await fetch(`${API_BASE}/recommend/${encodeURIComponent(trackId)}?topN=${topN}`, {
      headers: getAuthHeaders()
    }),
  )
  return Array.isArray(data) ? data : []
}

export async function getUserRecommendations(userId, topN = 10) {
  const data = await parseResponse(
    await fetch(`${API_BASE}/recommend/user/${encodeURIComponent(userId)}?topN=${topN}`, {
      headers: getAuthHeaders()
    }),
  )
  return Array.isArray(data) ? data : []
}

export async function getDemoUsers(limit = 8) {
  const data = await parseResponse(await fetch(`${API_BASE}/users/demo?limit=${limit}`))
  return Array.isArray(data) ? data : []
}

export async function submitFeedback(userId, trackId, feedbackType) {
  const response = await fetch(`${API_BASE}/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders()
    },
    body: JSON.stringify({ userId, trackId, feedbackType }),
  })
  return parseResponse(response)
}

export async function resetFeedback(userId) {
  const response = await fetch(`${API_BASE}/feedback/reset/${encodeURIComponent(userId)}`, {
    method: 'POST',
    headers: getAuthHeaders()
  })
  return parseResponse(response)
}

export async function searchYoutubeVideo(query) {
  const data = await parseResponse(
    await fetch(`${API_BASE}/youtube/search?q=${encodeURIComponent(query)}`)
  )
  return data.video_id || ''
}

export async function getBlendRecommendations(user1, user2, topN = 10) {
  const data = await parseResponse(
    await fetch(`${API_BASE}/recommend/blend?user1=${encodeURIComponent(user1)}&user2=${encodeURIComponent(user2)}&topN=${topN}`)
  )
  return data || { match_score: 0.5, recommendations: [] }
}
