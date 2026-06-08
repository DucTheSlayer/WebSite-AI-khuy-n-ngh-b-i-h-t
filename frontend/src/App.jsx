import { useEffect, useMemo, useState } from 'react'
import {
  getDemoUsers,
  getRecommendations,
  getUserRecommendations,
  searchSongs,
  submitFeedback,
  resetFeedback,
  searchYoutubeVideo,
  getBlendRecommendations
} from './api'

const DEMO_USER_LIMIT = 24
const WEB_USER_ID = 'demo_web_user'

const FRIEND_NAMES = [
  'Alex Mercer', 'Sarah Connor', 'Bruce Wayne', 'Clark Kent',
  'Peter Parker', 'Selina Kyle', 'Tony Stark', 'Natasha Romanoff',
  'Steve Rogers', 'Wanda Maximoff', 'Luke Skywalker', 'Leia Organa',
  'Han Solo', 'Frodo Baggins', 'Samwise Gamgee', 'Harry Potter',
  'Hermione Granger', 'Ron Weasley', 'Sherlock Holmes', 'John Watson',
  'Michael Scott', 'Jessica Alba', 'David Miller', 'Emily Watson'
]

function cleanDisplayText(value = '') {
  if (!/[ÃÂâ]/.test(value)) {
    return value
  }
  try {
    const bytes = Uint8Array.from([...value].map((character) => character.charCodeAt(0) & 255))
    return new TextDecoder('utf-8').decode(bytes)
  } catch {
    return value
  }
}

function formatDemoUsers(users) {
  return [...users]
    .sort((left, right) => (right.interactions ?? 0) - (left.interactions ?? 0))
    .map((user, index) => {
      const displayName = FRIEND_NAMES[index % FRIEND_NAMES.length] || `Friend ${index + 1}`
      const topArtists = (user.topArtists ?? []).map(cleanDisplayText).filter(Boolean)
      
      // Determine listening status (randomly offline or listening to one of their top artists)
      // To make it deterministic, we hash the userId
      let hash = 0
      const uid = user.userId || ''
      for (let i = 0; i < uid.length; i++) {
        hash = uid.charCodeAt(i) + ((hash << 5) - hash)
      }
      
      const isOnline = Math.abs(hash) % 10 < 8 // 80% online
      let listeningStatus = 'Offline'
      if (isOnline && topArtists.length > 0) {
        const artistIdx = Math.abs(hash * 31) % topArtists.length
        listeningStatus = `Listening to ${topArtists[artistIdx]}`
      } else if (isOnline) {
        listeningStatus = 'Online'
      }

      return {
        ...user,
        displayName,
        listeningStatus,
        shortId: user.userId?.slice(0, 10) ?? '',
        topArtists,
      }
    })
}

// Generate CSS Gradient Cover based on track name / track ID
function getMockCoverStyle(trackId, title = 'Song') {
  if (!trackId) return { background: 'linear-gradient(135deg, #282828, #121212)' }
  let hash = 0
  for (let i = 0; i < trackId.length; i++) {
    hash = trackId.charCodeAt(i) + ((hash << 5) - hash)
  }
  const h1 = Math.abs(hash) % 360
  const h2 = Math.abs(hash * 31) % 360
  const c1 = `hsl(${h1}, 70%, 45%)`
  const c2 = `hsl(${h2}, 80%, 20%)`
  return {
    background: `linear-gradient(135deg, ${c1}, ${c2})`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    fontWeight: '800',
    fontSize: '20px',
    textShadow: '0 2px 4px rgba(0,0,0,0.6)',
    borderRadius: '4px',
    userSelect: 'none',
    fontFamily: '"Space Grotesk", sans-serif'
  }
}

function getFirstLetter(title) {
  return String(title || 'S').trim().charAt(0).toUpperCase()
}

export default function App() {
  // Navigation tabs: 'home' | 'search' | 'library'
  const [activeTab, setActiveTab] = useState('home')
  
  const [query, setQuery] = useState('')
  const [userQuery, setUserQuery] = useState('')
  const [songs, setSongs] = useState([])
  const [popularSongs, setPopularSongs] = useState([])
  const [demoUsers, setDemoUsers] = useState([])
  
  const [selectedSong, setSelectedSong] = useState(null)
  const [selectedUser, setSelectedUser] = useState(null)
  const [recommendations, setRecommendations] = useState([])
  const [isBlendMode, setIsBlendMode] = useState(false)
  const [blendMatchScore, setBlendMatchScore] = useState(0)
  
  // Loading states
  const [songsLoading, setSongsLoading] = useState(false)
  const [usersLoading, setUsersLoading] = useState(false)
  const [recommendLoading, setRecommendLoading] = useState(false)
  const [error, setError] = useState('')
  
  // Real-time Player State
  const [playingSong, setPlayingSong] = useState(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playProgress, setPlayProgress] = useState(0) // percentage
  const [playSeconds, setPlaySeconds] = useState(0)
  const [playDuration, setPlayDuration] = useState(180) // total seconds of song
  const [volume, setVolume] = useState(70)
  const [isMuted, setIsMuted] = useState(false)
  
  // User Feedback State (Liked songs in this session)
  const [likedSongIds, setLikedSongIds] = useState(new Set())
  const [dislikedSongIds, setDislikedSongIds] = useState(new Set())

  // --- YOUTUBE PLAYER API INTEGRATION ---
  const [playerReady, setPlayerReady] = useState(false)

  // Load YouTube Iframe API on Mount
  useEffect(() => {
    if (!window.YT) {
      const tag = document.createElement('script')
      tag.src = 'https://www.youtube.com/iframe_api'
      const firstScriptTag = document.getElementsByTagName('script')[0]
      firstScriptTag.parentNode.insertBefore(tag, firstScriptTag)
    }
  }, [])

  // Create/Update YouTube Player when playingSong changes
  useEffect(() => {
    if (!playingSong) return

    const queryStr = `${playingSong.trackName} ${playingSong.artists || playingSong.artist}`

    async function loadSongVideo() {
      setError('')
      try {
        const videoId = await searchYoutubeVideo(queryStr)
        if (!videoId) {
          setError('Could not find corresponding YouTube video.')
          return
        }

        function initYoutubePlayer() {
          // If player already exists, load new videoId
          if (window.ytPlayerInstance && typeof window.ytPlayerInstance.loadVideoById === 'function') {
            window.ytPlayerInstance.loadVideoById({
              videoId: videoId,
              startSeconds: 0
            })
            setIsPlaying(true)
            return
          }

          // Initialize player into the target div
          window.ytPlayerInstance = new window.YT.Player('yt-player-iframe', {
            height: '100%',
            width: '100%',
            videoId: videoId,
            playerVars: {
              autoplay: 1,
              controls: 1, // Show controls for visualization
              rel: 0,
              showinfo: 0,
              enablejsapi: 1,
              origin: window.location.origin
            },
            events: {
              onReady: (event) => {
                setPlayerReady(true)
                event.target.setVolume(isMuted ? 0 : volume)
                event.target.playVideo()
                setIsPlaying(true)
              },
              onStateChange: (event) => {
                // event.data: 1 = PLAYING, 2 = PAUSED, 0 = ENDED
                if (event.data === 1) {
                  setIsPlaying(true)
                  const dur = event.target.getDuration()
                  if (dur) setPlayDuration(dur)
                } else if (event.data === 2) {
                  setIsPlaying(false)
                } else if (event.data === 0) {
                  setIsPlaying(false)
                  setPlayProgress(0)
                  setPlaySeconds(0)
                }
              }
            }
          })
        }

        if (window.YT && window.YT.Player) {
          initYoutubePlayer()
        } else {
          window.onYouTubeIframeAPIReady = initYoutubePlayer
        }
      } catch (err) {
        console.error("Failed to load YouTube video", err)
        setError("Error loading YouTube media.")
      }
    }

    loadSongVideo()
  }, [playingSong])

  // Sync Play/Pause with YouTube Player
  useEffect(() => {
    if (window.ytPlayerInstance && typeof window.ytPlayerInstance.playVideo === 'function') {
      if (isPlaying) {
        window.ytPlayerInstance.playVideo()
      } else {
        window.ytPlayerInstance.pauseVideo()
      }
    }
  }, [isPlaying])

  // Sync Volume with YouTube Player
  useEffect(() => {
    if (window.ytPlayerInstance && typeof window.ytPlayerInstance.setVolume === 'function') {
      if (isMuted) {
        window.ytPlayerInstance.setVolume(0)
      } else {
        window.ytPlayerInstance.setVolume(volume)
      }
    }
  }, [volume, isMuted])

  // Pull actual play time from YouTube Player
  useEffect(() => {
    let interval = null
    if (isPlaying && window.ytPlayerInstance && typeof window.ytPlayerInstance.getCurrentTime === 'function') {
      interval = setInterval(() => {
        try {
          const currentTime = window.ytPlayerInstance.getCurrentTime()
          const duration = window.ytPlayerInstance.getDuration() || 180
          setPlaySeconds(currentTime)
          setPlayDuration(duration)
          setPlayProgress((currentTime / duration) * 100)
        } catch (e) {
          // ignore
        }
      }, 500)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isPlaying])

  // Load Popular Songs & Demo Users on Mount
  useEffect(() => {
    let active = true
    async function loadInitialData() {
      try {
        const popResult = await searchSongs('')
        if (active) {
          setPopularSongs(popResult.slice(0, 8))
        }
      } catch (err) {
        console.error("Failed to load popular songs", err)
      }

      setUsersLoading(true)
      try {
        const usersResult = await getDemoUsers(DEMO_USER_LIMIT)
        if (active) {
          setDemoUsers(formatDemoUsers(usersResult))
        }
      } catch (err) {
        console.error("Failed to load demo users", err)
      } finally {
        if (active) setUsersLoading(false)
      }
    }
    loadInitialData()
    return () => {
      active = false
    }
  }, [])

  // Song Search with Debounce
  useEffect(() => {
    if (!query) {
      setSongs([])
      return
    }
    let active = true
    async function doSearch() {
      setSongsLoading(true)
      setError('')
      try {
        const result = await searchSongs(query)
        if (active) {
          setSongs(result)
        }
      } catch (loadError) {
        if (active) {
          setError('Could not load songs from Spring Boot API.')
        }
      } finally {
        if (active) {
          setSongsLoading(false)
        }
      }
    }
    const timeoutId = window.setTimeout(doSearch, 250)
    return () => {
      active = false
      window.clearTimeout(timeoutId)
    }
  }, [query])

  // Handle Play/Pause Click
  function handlePlaySong(song) {
    if (playingSong?.trackId === song.trackId) {
      setIsPlaying(!isPlaying)
    } else {
      setPlayingSong(song)
      setIsPlaying(true)
      setPlayProgress(0)
      setPlaySeconds(0)
    }
  }

  // Handle Song Selection for Recommendations
  async function handleSelectSong(song) {
    setIsBlendMode(false)
    setBlendMatchScore(0)
    setSelectedSong(song)
    setSelectedUser(null)
    setRecommendLoading(true)
    setError('')
    try {
      const result = await getRecommendations(song.trackId)
      setRecommendations(result)
      // Set to play as well
      setPlayingSong(song)
      setIsPlaying(true)
      setPlayProgress(0)
      setPlaySeconds(0)
    } catch (loadError) {
      setRecommendations([])
      setError('Could not load recommendations.')
    } finally {
      setRecommendLoading(false)
    }
  }

  // Handle User Selection for Personalized Recommendations
  async function handleSelectUser(user) {
    setIsBlendMode(false)
    setBlendMatchScore(0)
    setSelectedUser(user)
    setSelectedSong(null)
    setRecommendLoading(true)
    setError('')
    try {
      const result = await getUserRecommendations(user.userId)
      setRecommendations(result)
    } catch (loadError) {
      setRecommendations([])
      setError('Could not load personalized recommendations.')
    } finally {
      setRecommendLoading(false)
    }
  }

  async function handleCreateBlend(user) {
    setIsBlendMode(true)
    setSelectedUser(user)
    setSelectedSong(null)
    setRecommendLoading(true)
    setError('')
    try {
      const result = await getBlendRecommendations(WEB_USER_ID, user.userId)
      setRecommendations(result.recommendations || [])
      setBlendMatchScore(result.match_score ?? 0.5)
    } catch (loadError) {
      setRecommendations([])
      setError('Could not load blend recommendations.')
    } finally {
      setRecommendLoading(false)
    }
  }

  // Handle Like/Dislike Feedback (Real-time Feedback Loop)
  async function handleFeedback(song, type) {
    const userId = WEB_USER_ID // Always submit feedback for the web guest user
    const trackId = song.trackId

    try {
      await submitFeedback(userId, trackId, type)
      
      // Update local state
      if (type === 'LIKE') {
        const newLikes = new Set(likedSongIds)
        if (newLikes.has(trackId)) {
          newLikes.delete(trackId)
        } else {
          newLikes.add(trackId)
          dislikedSongIds.delete(trackId)
        }
        setLikedSongIds(newLikes)
      } else {
        const newDislikes = new Set(dislikedSongIds)
        if (newDislikes.has(trackId)) {
          newDislikes.delete(trackId)
        } else {
          newDislikes.add(trackId)
          likedSongIds.delete(trackId)
        }
        setDislikedSongIds(newDislikes)
      }

      // Re-trigger recommendation query
      if (isBlendMode && selectedUser) {
        const result = await getBlendRecommendations(WEB_USER_ID, selectedUser.userId)
        setRecommendations(result.recommendations || [])
        setBlendMatchScore(result.match_score ?? 0.5)
      } else if (selectedUser) {
        const result = await getUserRecommendations(selectedUser.userId)
        setRecommendations(result)
      } else if (selectedSong) {
        const result = await getRecommendations(selectedSong.trackId)
        setRecommendations(result)
      }
    } catch (err) {
      console.error("Failed to submit feedback", err)
      setError("Failed to record feedback.")
    }
  }

  // Reset all feedbacks for current profile
  async function handleResetFeedback() {
    const userId = WEB_USER_ID // Always reset the guest user's preferences
    try {
      await resetFeedback(userId)
      setLikedSongIds(new Set())
      setDislikedSongIds(new Set())
      setError('')
      
      // Reload recommendations
      if (isBlendMode && selectedUser) {
        const result = await getBlendRecommendations(WEB_USER_ID, selectedUser.userId)
        setRecommendations(result.recommendations || [])
        setBlendMatchScore(result.match_score ?? 0.5)
      } else if (selectedUser) {
        const result = await getUserRecommendations(selectedUser.userId)
        setRecommendations(result)
      } else if (selectedSong) {
        const result = await getRecommendations(selectedSong.trackId)
        setRecommendations(result)
      }
    } catch (err) {
      console.error("Failed to reset feedback", err)
    }
  }

  const visibleDemoUsers = useMemo(() => {
    const normalizedQuery = userQuery.trim().toLowerCase()
    if (!normalizedQuery) return demoUsers

    return demoUsers.filter((user) => {
      const searchableProfile = [
        user.displayName,
        user.userId,
        user.shortId,
        ...(user.topArtists ?? []),
      ].join(' ').toLowerCase()

      return searchableProfile.includes(normalizedQuery)
    })
  }, [demoUsers, userQuery])

  // Mock Audio Features for current playing/selected song
  const mockAudioFeatures = useMemo(() => {
    const song = selectedSong || playingSong
    if (!song) return null

    let hash = 0
    const tid = song.trackId || ''
    for (let i = 0; i < tid.length; i++) {
      hash = tid.charCodeAt(i) + ((hash << 5) - hash)
    }
    
    return {
      danceability: Math.abs(hash % 45 + 45) / 100,
      energy: Math.abs((hash * 7) % 50 + 40) / 100,
      valence: Math.abs((hash * 13) % 60 + 30) / 100,
      acousticness: Math.abs((hash * 19) % 80 + 10) / 100,
      tempo: Math.abs((hash * 29) % 80 + 80),
    }
  }, [selectedSong, playingSong])

  // Formatting helper for time (seconds -> MM:SS)
  function formatTime(seconds) {
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="spotify-layout">
      {/* 1. SIDEBAR PANEL */}
      <aside className="spotify-sidebar">
        <div className="sidebar-logo">
          <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
            <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm4.586 14.424c-.18.295-.565.387-.86.207-2.377-1.454-5.37-1.783-8.893-.982-.336.075-.668-.135-.744-.47-.077-.337.135-.669.47-.745 3.848-.877 7.14-.5 9.822 1.14.296.18.387.563.205.85zm1.224-2.723c-.226.367-.707.487-1.074.26-2.72-1.672-6.87-2.157-10.076-1.183-.412.125-.845-.107-.97-.52-.125-.413.107-.847.52-.972 3.666-1.112 8.243-.573 11.34 1.33.367.227.487.708.26 1.085zm.106-2.825C14.498 8.766 8.795 8.577 5.5 9.578c-.506.153-1.04-.137-1.193-.642-.153-.505.137-1.04.642-1.193 3.79-1.148 10.09-.927 14.05 1.424.455.27.604.856.334 1.312-.27.455-.856.604-1.312.334z"/>
          </svg>
          <h2>SpotiAI</h2>
        </div>

        <nav className="sidebar-menu">
          <button 
            type="button" 
            className={`menu-item ${activeTab === 'home' ? 'active' : ''}`}
            onClick={() => setActiveTab('home')}
          >
            <span className="icon">🏠</span> Home
          </button>
          <button 
            type="button" 
            className={`menu-item ${activeTab === 'search' ? 'active' : ''}`}
            onClick={() => setActiveTab('search')}
          >
            <span className="icon">🔍</span> Search
          </button>
          <button 
            type="button" 
            className={`menu-item ${activeTab === 'users' ? 'active' : ''}`}
            onClick={() => setActiveTab('users')}
          >
            <span className="icon">👥</span> Friend Activity
          </button>
        </nav>

        {/* Mini Library info / Liked songs count */}
        <div className="sidebar-library">
          <div className="library-header">
            <span>📚 Your Library</span>
          </div>
          <div className="library-items">
            <button 
              type="button" 
              className={`library-item-card ${activeTab === 'liked' ? 'active' : ''}`}
              onClick={() => setActiveTab('liked')}
            >
              <div className="heart-icon-box">❤️</div>
              <div>
                <strong>Liked Songs</strong>
                <p>{likedSongIds.size} songs</p>
              </div>
            </button>
          </div>
        </div>

        {/* YouTube Mini Video Embed Box */}
        {playingSong && (
          <div className="sidebar-mini-player">
            <div className="mini-player-header">
              <span>Now Playing MV</span>
            </div>
            <div className="mini-player-video-box">
              <div id="yt-player-iframe"></div>
            </div>
          </div>
        )}
      </aside>

      {/* 2. MAIN CONTENT AREA */}
      <main className="spotify-main">
        {/* Dynamic header background gradient */}
        <header className="main-header" style={{
          background: selectedSong 
            ? `linear-gradient(to bottom, ${getMockCoverStyle(selectedSong.trackId).background.split('(')[1].split(',')[0]}, #121212)`
            : selectedUser 
              ? 'linear-gradient(to bottom, #1e3264, #121212)'
              : 'linear-gradient(to bottom, #222222, #121212)'
        }}>
          <div className="header-navigation">
            <span className="badge">GRADUATION PROJECT</span>
            {error && <span className="error-badge">{error}</span>}
          </div>

          <div className="header-banner-content">
            {selectedSong && (
              <div className="banner-details">
                <div className="banner-cover" style={getMockCoverStyle(selectedSong.trackId, selectedSong.trackName)}>
                  {getFirstLetter(selectedSong.trackName)}
                </div>
                <div>
                  <span className="eyebrow-text">SONG RECOMMENDATION MODE</span>
                  <h1 className="banner-title">{selectedSong.trackName}</h1>
                  <p className="banner-meta">
                    <strong>{selectedSong.artists || selectedSong.artist}</strong> • {selectedSong.trackGenre || selectedSong.genre} • Popularity: {selectedSong.popularity}
                  </p>
                </div>
              </div>
            )}

            {selectedUser && (
              <div className="banner-details">
                {isBlendMode ? (
                  <div className="blend-avatar-container">
                    <div className="avatar-overlap you-avatar">👤</div>
                    <div className="avatar-overlap friend-avatar">👥</div>
                  </div>
                ) : (
                  <div className="banner-cover user-avatar-cover">
                    👤
                  </div>
                )}
                <div>
                  <span className="eyebrow-text">
                    {isBlendMode ? "MUTUAL MUSIC BLEND MODE" : "FRIEND ACTIVITY MODE"}
                  </span>
                  <h1 className="banner-title">
                    {isBlendMode ? `You & ${selectedUser.displayName}` : selectedUser.displayName}
                  </h1>
                  <p className="banner-meta">
                    {isBlendMode ? (
                      <>
                        Taste Match Score: <strong className="status-badge-online">{Math.round(blendMatchScore * 100)}%</strong> • Shared Discoveries
                      </>
                    ) : (
                      <>
                        Status: <span className="status-badge-online">{selectedUser.listeningStatus}</span> • Last.fm ID: <span className="mono-id">{selectedUser.shortId}...</span> • Interactions: <strong>{selectedUser.interactions} artists</strong>
                      </>
                    )}
                  </p>
                  {!isBlendMode && (
                    <button 
                      type="button" 
                      className="create-blend-btn"
                      onClick={() => handleCreateBlend(selectedUser)}
                    >
                      🔗 Create a Blend Playlist
                    </button>
                  )}
                </div>
              </div>
            )}

            {!selectedSong && !selectedUser && (
              <div className="banner-details">
                <div>
                  <span className="eyebrow-text">WELCOME</span>
                  <h1 className="banner-title">SpotiAI Recommender</h1>
                  <p className="banner-meta">
                    A Premium Music Recommender Engine blending Spotify audio features and Last.fm collaborative weights.
                  </p>
                </div>
              </div>
            )}
          </div>
        </header>

        {/* Tab-based View router */}
        <div className="main-content-scroll">
          {/* TAB 1: HOME PAGE */}
          {activeTab === 'home' && (
            <div className="tab-pane home-pane">
              <section className="dashboard-section">
                <h2>Good evening</h2>
                <div className="quick-grid">
                  {popularSongs.slice(0, 6).map((song) => (
                    <div key={song.trackId} className="quick-card" onClick={() => handleSelectSong(song)}>
                      <div className="quick-card-cover" style={getMockCoverStyle(song.trackId, song.trackName)}>
                        {getFirstLetter(song.trackName)}
                      </div>
                      <div className="quick-card-info">
                        <strong>{song.trackName}</strong>
                        <p>{song.artists}</p>
                      </div>
                      <button 
                        type="button" 
                        className="play-hover-btn" 
                        onClick={(e) => {
                          e.stopPropagation()
                          handlePlaySong(song)
                        }}
                      >
                        {playingSong?.trackId === song.trackId && isPlaying ? '⏸️' : '▶️'}
                      </button>
                    </div>
                  ))}
                </div>
              </section>

              <section className="dashboard-section">
                <div className="section-title-row">
                  <h2>Popular on SpotiAI</h2>
                </div>
                <div className="premium-grid">
                  {popularSongs.map((song) => (
                    <div key={song.trackId} className="song-grid-card" onClick={() => handleSelectSong(song)}>
                      <div className="grid-card-cover-wrapper">
                        <div className="grid-card-cover" style={getMockCoverStyle(song.trackId, song.trackName)}>
                          {getFirstLetter(song.trackName)}
                        </div>
                        <button 
                          type="button" 
                          className="play-grid-btn"
                          onClick={(e) => {
                            e.stopPropagation()
                            handlePlaySong(song)
                          }}
                        >
                          {playingSong?.trackId === song.trackId && isPlaying ? '⏸️' : '▶️'}
                        </button>
                      </div>
                      <div className="grid-card-info">
                        <strong>{song.trackName}</strong>
                        <p>{song.artists}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}

          {/* TAB 2: SEARCH SONG PAGE */}
          {activeTab === 'search' && (
            <div className="tab-pane search-pane">
              <div className="search-bar-wrapper">
                <span className="search-icon">🔍</span>
                <input 
                  type="text" 
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="What do you want to listen to? (e.g. Comedy, pop, acoustic...)" 
                  autoFocus
                />
              </div>

              {songsLoading && <p className="loading-text">Searching song catalog...</p>}

              {songs.length > 0 && (
                <section className="dashboard-section">
                  <h2>Search Results</h2>
                  <div className="playlist-table-wrapper">
                    <table className="playlist-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Title</th>
                          <th>Album</th>
                          <th>Genre</th>
                          <th className="center-cell">Popularity</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {songs.map((song, index) => (
                          <tr key={song.trackId} onClick={() => handleSelectSong(song)} className={selectedSong?.trackId === song.trackId ? 'selected-row' : ''}>
                            <td className="row-number-col">
                              <span className="index-num">{index + 1}</span>
                              <button 
                                type="button" 
                                className="row-play-btn"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handlePlaySong(song)
                                }}
                              >
                                {playingSong?.trackId === song.trackId && isPlaying ? '⏸️' : '▶️'}
                              </button>
                            </td>
                            <td>
                              <div className="song-title-cell">
                                <div className="song-mini-cover" style={getMockCoverStyle(song.trackId, song.trackName)}>
                                  {getFirstLetter(song.trackName)}
                                </div>
                                <div>
                                  <strong className="song-name-link">{song.trackName}</strong>
                                  <p className="song-artist-sub">{song.artists}</p>
                                </div>
                              </div>
                            </td>
                            <td className="gray-text">{song.albumName || 'Spotify Album'}</td>
                            <td><span className="genre-label">{song.trackGenre || 'unknown'}</span></td>
                            <td className="center-cell">{song.popularity}</td>
                            <td onClick={(e) => e.stopPropagation()}>
                              <div className="row-actions">
                                <button 
                                  type="button" 
                                  className={`action-btn-heart ${likedSongIds.has(song.trackId) ? 'liked' : ''}`}
                                  onClick={() => handleFeedback(song, 'LIKE')}
                                >
                                  💚
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {!songsLoading && query && songs.length === 0 && (
                <p className="empty-state">No songs match your query. Try something else.</p>
              )}
            </div>
          )}

          {/* TAB 3: FRIEND ACTIVITY */}
          {activeTab === 'users' && (
            <div className="tab-pane users-pane">
              <div className="search-bar-wrapper">
                <span className="search-icon">🔍</span>
                <input 
                  type="text" 
                  value={userQuery}
                  onChange={(e) => setUserQuery(e.target.value)}
                  placeholder="Search friends by name, artist, or listener id..." 
                />
              </div>

              {usersLoading && <p className="loading-text">Connecting to Friend Activity Feed...</p>}

              <div className="profile-grid">
                {visibleDemoUsers.map((user) => {
                  const isOffline = user.listeningStatus === 'Offline'
                  return (
                    <div 
                      key={user.userId} 
                      className={`profile-card ${selectedUser?.userId === user.userId ? 'active' : ''}`}
                      onClick={() => {
                        handleSelectUser(user)
                      }}
                    >
                      <div className={`profile-avatar ${isOffline ? 'offline' : 'online'}`}>
                        👤
                        <span className={`status-indicator ${isOffline ? 'offline' : 'online'}`}></span>
                      </div>
                      <h3>{user.displayName}</h3>
                      <p className={`profile-status-text ${isOffline ? 'offline' : 'online'}`}>
                        {user.listeningStatus}
                      </p>
                      <p className="profile-sub">{user.interactions} artist interactions</p>
                      <p className="profile-hash">ID: {user.shortId}...</p>
                      <div className="top-artists-chips">
                        {user.topArtists.slice(0, 3).map((artist) => (
                          <span key={artist} className="artist-chip">{artist}</span>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
              
              {!usersLoading && visibleDemoUsers.length === 0 && (
                <p className="empty-state">No friends found matching that query.</p>
              )}
            </div>
          )}

          {/* TAB 4: LIKED SONGS PAGE */}
          {activeTab === 'liked' && (
            <div className="tab-pane liked-pane">
              <h2>Liked Songs</h2>
              {likedSongIds.size === 0 ? (
                <p className="empty-state">Songs you like will appear here. Try liking some recommendations!</p>
              ) : (
                <div className="playlist-table-wrapper">
                  <table className="playlist-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Title</th>
                        <th>Genre</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...likedSongIds].map((trackId, index) => {
                        const song = popularSongs.find(s => s.trackId === trackId) 
                                      || songs.find(s => s.trackId === trackId)
                                      || recommendations.find(s => s.trackId === trackId)
                                      || { trackId, trackName: 'Liked Song', artists: 'Various Artists', trackGenre: 'Favorite' }
                        return (
                          <tr key={trackId} onClick={() => handleSelectSong(song)}>
                            <td className="row-number-col">{index + 1}</td>
                            <td>
                              <div className="song-title-cell">
                                <div className="song-mini-cover" style={getMockCoverStyle(song.trackId, song.trackName)}>
                                  {getFirstLetter(song.trackName)}
                                </div>
                                <div>
                                  <strong>{song.trackName}</strong>
                                  <p className="song-artist-sub">{song.artists || song.artist}</p>
                                </div>
                              </div>
                            </td>
                            <td><span className="genre-label">{song.trackGenre || song.genre}</span></td>
                            <td onClick={(e) => e.stopPropagation()}>
                              <button 
                                type="button"
                                className="action-btn-heart liked"
                                onClick={() => handleFeedback(song, 'LIKE')}
                              >
                                💚
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* RECOMMENDATIONS WORKSPACE */}
          {(selectedSong || selectedUser) && (
            <div className="recommendations-workspace">
              {/* Reset Feedback Control panel */}
              <div className="feedback-control-bar">
                <div className="control-bar-info">
                  <strong>💡 Active Mode: </strong>
                  <span>{isBlendMode ? `Blend (You & ${selectedUser.displayName})` : selectedUser ? `${selectedUser.displayName} (Friend)` : 'Guest listener'}</span>
                  { (likedSongIds.size > 0 || dislikedSongIds.size > 0) && (
                    <span className="feedback-badge">({likedSongIds.size} likes, {dislikedSongIds.size} dislikes)</span>
                  )}
                </div>
                <button 
                  type="button" 
                  className="reset-btn"
                  onClick={handleResetFeedback}
                >
                  🔄 Reset Taste Preferences
                </button>
              </div>

              {/* Grid workspace containing: 1. Recommendations table, 2. Audio features visualizer */}
              <div className="recommendations-container">
                <div className="recommendations-list-section">
                  <div className="panel-sub-header">
                    <h2>Recommended Songs</h2>
                    <span>{recommendLoading ? 'Calculating similarity scores...' : `${recommendations.length} tracks matched`}</span>
                  </div>

                  {recommendations.length > 0 ? (
                    <div className="playlist-table-wrapper">
                      <table className="playlist-table">
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>Title</th>
                            <th>Genre</th>
                            <th>Match Score</th>
                            <th>Reason & Explanation</th>
                            <th>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {recommendations.map((item, index) => {
                            const isLiked = likedSongIds.has(item.trackId)
                            const isDisliked = dislikedSongIds.has(item.trackId)
                            return (
                              <tr 
                                key={item.trackId} 
                                className={`rec-row ${isDisliked ? 'disliked-row' : ''}`}
                                onClick={() => {
                                  if (!isDisliked) handleSelectSong(item)
                                }}
                              >
                                <td className="row-number-col">
                                  <span className="index-num">{index + 1}</span>
                                  {!isDisliked && (
                                    <button 
                                      type="button" 
                                      className="row-play-btn"
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        handlePlaySong(item)
                                      }}
                                    >
                                      {playingSong?.trackId === item.trackId && isPlaying ? '⏸️' : '▶️'}
                                    </button>
                                  )}
                                </td>
                                <td>
                                  <div className="song-title-cell">
                                    <div className="song-mini-cover" style={getMockCoverStyle(item.trackId, item.trackName)}>
                                      {getFirstLetter(item.trackName)}
                                    </div>
                                    <div>
                                      <strong>{item.trackName}</strong>
                                      <p className="song-artist-sub">
                                        {item.artist}
                                        {isBlendMode && item.matchType && (
                                          <span className={`blend-match-tag ${item.matchType.toLowerCase()}`}>
                                            {item.matchType === 'BOTH' ? '🟣 Blend' : item.matchType === 'USER1' ? '🟢 You' : `🔵 ${selectedUser.displayName.split(' ')[0]}`}
                                          </span>
                                        )}
                                      </p>
                                    </div>
                                  </div>
                                </td>
                                <td><span className="genre-label">{item.genre || 'unknown'}</span></td>
                                <td>
                                  <span className="score-badge">
                                    {Number(item.score ?? 0).toFixed(4)}
                                  </span>
                                </td>
                                <td className="explanation-cell">
                                  <span className="reason-text">{item.reason}</span>
                                </td>
                                <td onClick={(e) => e.stopPropagation()}>
                                  <div className="row-feedback-actions">
                                    <button 
                                      type="button" 
                                      className={`action-btn-heart ${isLiked ? 'liked' : ''}`}
                                      title="Like this recommendation (weights profile closer)"
                                      onClick={() => handleFeedback(item, 'LIKE')}
                                    >
                                      {isLiked ? '💚' : '♡'}
                                    </button>
                                    <button 
                                      type="button" 
                                      className={`action-btn-dislike ${isDisliked ? 'active' : ''}`}
                                      title="Dislike this recommendation (banishes track instantly)"
                                      onClick={() => handleFeedback(item, 'DISLIKE')}
                                    >
                                      🚫
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    !recommendLoading && <p className="empty-state">No recommendations available for this entity.</p>
                  )}
                </div>

                {/* Right Panel: Audio Features Analysis */}
                {mockAudioFeatures && (
                  <div className="audio-features-panel">
                    <h3>Acoustic Signature</h3>
                    <p className="features-sub">Interactive feature analysis for current selected track</p>
                    
                    <div className="feature-bars">
                      <div className="feature-bar-group">
                        <div className="feature-label-row">
                          <span>Danceability</span>
                          <strong>{Math.round(mockAudioFeatures.danceability * 100)}%</strong>
                        </div>
                        <div className="progress-bar-bg">
                          <div className="progress-bar-fill" style={{ width: `${mockAudioFeatures.danceability * 100}%`, backgroundColor: '#1ed760' }}></div>
                        </div>
                      </div>

                      <div className="feature-bar-group">
                        <div className="feature-label-row">
                          <span>Energy (Intensity)</span>
                          <strong>{Math.round(mockAudioFeatures.energy * 100)}%</strong>
                        </div>
                        <div className="progress-bar-bg">
                          <div className="progress-bar-fill" style={{ width: `${mockAudioFeatures.energy * 100}%`, backgroundColor: '#ff9e6d' }}></div>
                        </div>
                      </div>

                      <div className="feature-bar-group">
                        <div className="feature-label-row">
                          <span>Valence (Mood Positivity)</span>
                          <strong>{Math.round(mockAudioFeatures.valence * 100)}%</strong>
                        </div>
                        <div className="progress-bar-bg">
                          <div className="progress-bar-fill" style={{ width: `${mockAudioFeatures.valence * 100}%`, backgroundColor: '#ffd38b' }}></div>
                        </div>
                      </div>

                      <div className="feature-bar-group">
                        <div className="feature-label-row">
                          <span>Acousticness</span>
                          <strong>{Math.round(mockAudioFeatures.acousticness * 100)}%</strong>
                        </div>
                        <div className="progress-bar-bg">
                          <div className="progress-bar-fill" style={{ width: `${mockAudioFeatures.acousticness * 100}%`, backgroundColor: '#7cc4ff' }}></div>
                        </div>
                      </div>

                      <div className="tempo-box">
                        <span className="tempo-label">Estimated Tempo</span>
                        <strong className="tempo-value">{Math.round(mockAudioFeatures.tempo)} <span className="bpm">BPM</span></strong>
                      </div>
                    </div>

                    <div className="algorithm-card">
                      <h4>📊 Behind the algorithm</h4>
                      <p>
                        Our content vector space measures Euclidean and Cosine distances over 15 standardized Spotify metrics. 
                        By combining these features with collaborative user profile weights, SpotiAI balances melodic structure and listener demographics.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* 3. NOW PLAYING CONTROLS BAR (Bottom Player) */}
      <footer className="spotify-player-bar">
        {/* Left Side: Playing Song info */}
        <div className="player-song-details">
          {playingSong ? (
            <>
              <div className="player-cover" style={getMockCoverStyle(playingSong.trackId, playingSong.trackName)}>
                {getFirstLetter(playingSong.trackName)}
              </div>
              <div className="player-song-meta">
                <strong className="song-title-playing">{playingSong.trackName}</strong>
                <p className="song-artist-playing">{playingSong.artists || playingSong.artist}</p>
              </div>
              <button 
                type="button" 
                className={`player-heart-btn ${likedSongIds.has(playingSong.trackId) ? 'liked' : ''}`}
                onClick={() => handleFeedback(playingSong, 'LIKE')}
              >
                {likedSongIds.has(playingSong.trackId) ? '💚' : '♡'}
              </button>
            </>
          ) : (
            <div className="player-no-song">No track selected</div>
          )}
        </div>

        {/* Center Side: Media controls */}
        <div className="player-controls-wrapper">
          <div className="player-control-buttons">
            <button type="button" className="control-btn" title="Shuffle">🔀</button>
            <button type="button" className="control-btn" title="Previous">⏮️</button>
            <button 
              type="button" 
              className="player-play-pause-btn"
              disabled={!playingSong}
              onClick={() => setIsPlaying(!isPlaying)}
            >
              {isPlaying ? '⏸️' : '▶️'}
            </button>
            <button type="button" className="control-btn" title="Next">⏭️</button>
            <button type="button" className="control-btn" title="Repeat">🔁</button>
          </div>

          <div className="player-progress-bar-row">
            <span className="time-text">{formatTime(playSeconds)}</span>
            <div className="player-progress-bg" onClick={(e) => {
              if (window.ytPlayerInstance && typeof window.ytPlayerInstance.seekTo === 'function') {
                const rect = e.currentTarget.getBoundingClientRect()
                const pct = (e.clientX - rect.left) / rect.width
                try {
                  const duration = window.ytPlayerInstance.getDuration() || 180
                  window.ytPlayerInstance.seekTo(pct * duration, true)
                  setPlayProgress(pct * 100)
                  setPlaySeconds(pct * duration)
                } catch (err) {
                  // ignore
                }
              }
            }}>
              <div className="player-progress-fill" style={{ width: `${playProgress}%` }}></div>
            </div>
            <span className="time-text">{formatTime(playDuration)}</span>
          </div>
        </div>

        {/* Right Side: Volume controls */}
        <div className="player-volume-controls">
          <button type="button" className="control-btn" onClick={() => setIsMuted(!isMuted)}>
            {isMuted || volume === 0 ? '🔇' : volume < 40 ? '🔉' : '🔊'}
          </button>
          <div className="volume-slider-bg" onClick={(e) => {
            if (window.ytPlayerInstance && typeof window.ytPlayerInstance.setVolume === 'function') {
              const rect = e.currentTarget.getBoundingClientRect()
              const vol = Math.round(((e.clientX - rect.left) / rect.width) * 100)
              setVolume(Math.max(0, Math.min(100, vol)))
              setIsMuted(false)
            }
          }}>
            <div className="volume-slider-fill" style={{ width: `${isMuted ? 0 : volume}%` }}></div>
          </div>
        </div>
      </footer>
    </div>
  )
}
