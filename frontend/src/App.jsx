import { useEffect, useMemo, useState } from 'react'
import {
  getDemoUsers,
  getRecommendations,
  getUserRecommendations,
  searchSongs,
  submitFeedback,
  resetFeedback,
  searchYoutubeVideo,
  getBlendRecommendations,
  login as apiLogin,
  register as apiRegister,
  getMe as apiGetMe,
  logout as apiLogout
} from './api'
import {
  cleanDisplayText,
  formatDemoUsers,
  getMockCoverStyle,
  getFirstLetter
} from './utils'

const DEMO_USER_LIMIT = 24
const WEB_USER_ID = 'demo_web_user'


export default function App() {
  // --- 1. KHAI BÁO CÁC STATE (TRẠNG THÁI) TRONG REACT ---
  // useState dùng để lưu trữ dữ liệu có thể thay đổi và yêu cầu giao diện vẽ lại (re-render) khi dữ liệu đó thay đổi.

  // Tab hiện tại đang mở trên thanh menu bên trái ('home', 'search', 'users', 'liked')
  const [activeTab, setActiveTab] = useState('home')
  
  // Từ khóa tìm kiếm bài hát do người dùng nhập vào ô tìm kiếm
  const [query, setQuery] = useState('')
  // Từ khóa tìm kiếm bạn bè trong tab Friend Activity
  const [userQuery, setUserQuery] = useState('')
  // Danh sách bài hát kết quả tìm kiếm được trả về từ Backend Spring Boot
  const [songs, setSongs] = useState([])
  // Danh sách bài hát phổ biến hiển thị ở trang chủ mặc định
  const [popularSongs, setPopularSongs] = useState([])
  // Danh sách người dùng Last.fm giả lập để demo tính năng gợi ý
  const [demoUsers, setDemoUsers] = useState([])
  
  // Bài hát đang được chọn để xem danh sách gợi ý liên quan (Song Mode)
  const [selectedSong, setSelectedSong] = useState(null)
  // Bạn bè đang được chọn để xem danh sách gợi ý cá nhân hóa (User Mode)
  const [selectedUser, setSelectedUser] = useState(null)
  // Danh sách các bài hát được gợi ý tương ứng (Song Mode / User Mode / Blend Mode)
  const [recommendations, setRecommendations] = useState([])
  // Trạng thái bật/tắt chế độ Blend (trộn gu nhạc giữa bạn và 1 người bạn)
  const [isBlendMode, setIsBlendMode] = useState(false)
  // Điểm số tương thích âm nhạc (%) giữa bạn và người bạn được chọn trong chế độ Blend
  const [blendMatchScore, setBlendMatchScore] = useState(0)
  
  // --- CÁC TRẠNG THÁI HIỂN THỊ LOADING (ĐANG TẢI DỮ LIỆU) ---
  const [songsLoading, setSongsLoading] = useState(false) // Đang tìm kiếm bài hát
  const [usersLoading, setUsersLoading] = useState(false)   // Đang tải danh sách bạn bè
  const [recommendLoading, setRecommendLoading] = useState(false) // Đang chạy thuật toán gợi ý AI
  const [error, setError] = useState('') // Lưu trữ thông điệp lỗi nếu có lỗi API xảy ra
  
  // --- TRẠNG THÁI TRÌNH PHÁT NHẠC PLAYER (BOTTOM BAR) CHẠY THỜI GIAN THỰC ---
  const [playingSong, setPlayingSong] = useState(null) // Bài hát hiện đang được phát nhạc
  const [isPlaying, setIsPlaying] = useState(false)     // Nhạc đang phát (true) hay tạm dừng (false)
  const [playProgress, setPlayProgress] = useState(0)  // Tiến trình chạy bài hát dạng % (0 - 100)
  const [playSeconds, setPlaySeconds] = useState(0)    // Số giây hiện tại của bài hát đang phát
  const [playDuration, setPlayDuration] = useState(180) // Tổng số giây của bài hát hiện tại
  const [volume, setVolume] = useState(70)             // Âm lượng trình phát nhạc (0 - 100)
  const [isMuted, setIsMuted] = useState(false)         // Trạng thái tắt tiếng (Mute)
  
  // --- PHẢN HỒI GU NHẠC CỦA TÀI KHOẢN ĐANG ĐĂNG NHẬP ---
  // Sử dụng đối tượng Set trong JavaScript để lưu danh sách ID bài hát đã Thích (Like) hoặc Ghét (Dislike) độc nhất.
  const [likedSongIds, setLikedSongIds] = useState(new Set())
  const [dislikedSongIds, setDislikedSongIds] = useState(new Set())

  // --- TRẠNG THÁI ĐĂNG NHẬP / THÀNH VIÊN ---
  const [currentUser, setCurrentUser] = useState(null) // Thông tin tài khoản người dùng đang đăng nhập
  const [personalRecommendations, setPersonalRecommendations] = useState([]) // Danh sách 8 bài hát gợi ý riêng cho bạn ở trang chủ
  
  // Trạng thái hiển thị Form đăng nhập/đăng ký ('login' | 'register' | null nếu đóng)
  const [authModalOpen, setAuthModalOpen] = useState(null)
  const [authError, setAuthError] = useState('') // Lỗi đăng nhập hoặc đăng ký
  // Các ô input trong form xác thực
  const [authUsername, setAuthUsername] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authEmail, setAuthEmail] = useState('')
  const [authFullName, setAuthFullName] = useState('')

  // --- TÍCH HỢP YOUTUBE PLAYER API QUA IFRAME CHẠY NGẦM ---
  const [playerReady, setPlayerReady] = useState(false)

  // useEffect này chạy 1 lần duy nhất khi ứng dụng bắt đầu (Component Mount) để nhúng file script của YouTube Iframe API vào HTML.
  // Điều này cho phép chúng ta điều khiển phát nhạc, tua nhanh, tăng giảm âm lượng thông qua mã JavaScript.
  useEffect(() => {
    if (!window.YT) {
      const tag = document.createElement('script')
      tag.src = 'https://www.youtube.com/iframe_api'
      const firstScriptTag = document.getElementsByTagName('script')[0]
      firstScriptTag.parentNode.insertBefore(tag, firstScriptTag)
    }
  }, [])

  // Tự động kiểm tra Token đăng nhập trong localStorage khi ứng dụng khởi chạy.
  // Nếu có token hợp lệ, hệ thống sẽ tự động gọi API lấy thông tin người dùng và gu nhạc của họ mà không bắt đăng nhập lại.
  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      apiGetMe()
        .then((userData) => {
          setCurrentUser(userData)
          // Đọc danh sách đã like và dislike từ tài khoản lưu trữ
          if (userData.likedSongIds) {
            setLikedSongIds(new Set(userData.likedSongIds))
          }
          if (userData.dislikedSongIds) {
            setDislikedSongIds(new Set(userData.dislikedSongIds))
          }
          // Tải danh sách gợi ý dành riêng cho tài khoản này
          loadPersonalRecommendations(userData.username)
        })
        .catch(() => {
          // Token hết hạn hoặc không hợp lệ -> Xóa bỏ token để tránh lỗi vòng lặp
          localStorage.removeItem('token')
        })
    }
  }, [])

  // Hàm gọi API lấy danh sách bài hát gợi ý cá nhân hóa dựa trên gu nhạc hiện tại của người dùng.
  async function loadPersonalRecommendations(username) {
    try {
      const result = await getUserRecommendations(username, 8)
      setPersonalRecommendations(result)
    } catch (err) {
      console.error("Không thể tải danh sách gợi ý cá nhân hóa", err)
    }
  }

  // Tự động tìm kiếm video trên YouTube và khởi tạo/cập nhật trình phát nhạc YouTube mỗi khi bài hát đang nghe (playingSong) thay đổi.
  useEffect(() => {
    if (!playingSong) return

    // Tạo từ khóa tìm kiếm: "Tên bài hát Tên ca sĩ" để đảm bảo tìm đúng MV trên YouTube
    const queryStr = `${playingSong.trackName} ${playingSong.artists || playingSong.artist}`

    async function loadSongVideo() {
      setError('')
      try {
        // Gọi API cào (scrape) YouTube để lấy video_id đầu tiên khớp với từ khóa
        const videoId = await searchYoutubeVideo(queryStr)
        if (!videoId) {
          setError('Không tìm thấy video tương ứng trên YouTube.')
          return
        }

        // Hàm khởi tạo đối tượng YouTube Player điều khiển Iframe
        function initYoutubePlayer() {
          // Nếu trình phát đã được tạo từ trước, chỉ cần yêu cầu phát video mới
          if (window.ytPlayerInstance && typeof window.ytPlayerInstance.loadVideoById === 'function') {
            window.ytPlayerInstance.loadVideoById({
              videoId: videoId,
              startSeconds: 0
            })
            setIsPlaying(true)
            return
          }

          // Tạo mới đối tượng YouTube Player nhắm vào thẻ div có id 'yt-player-iframe'
          window.ytPlayerInstance = new window.YT.Player('yt-player-iframe', {
            height: '100%',
            width: '100%',
            videoId: videoId,
            playerVars: {
              autoplay: 1,      // Tự động phát video ngay khi tải xong
              controls: 1,      // Hiện thanh điều khiển chuẩn của YouTube để hỗ trợ trực quan
              rel: 0,           // Không hiển thị video liên quan từ kênh khác
              showinfo: 0,
              enablejsapi: 1,   // Bật API JavaScript để điều khiển
              origin: window.location.origin
            },
            events: {
              // Khi trình phát đã sẵn sàng hoạt động
              onReady: (event) => {
                setPlayerReady(true)
                // Đồng bộ âm lượng hiện tại
                event.target.setVolume(isMuted ? 0 : volume)
                event.target.playVideo()
                setIsPlaying(true)
              },
              // Khi trạng thái video thay đổi (Đang phát, tạm dừng, kết thúc)
              onStateChange: (event) => {
                // event.data: 1 = Đang phát (PLAYING), 2 = Tạm dừng (PAUSED), 0 = Kết thúc (ENDED)
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

        // Đảm bảo Script YouTube API đã sẵn sàng rồi mới khởi tạo player
        if (window.YT && window.YT.Player) {
          initYoutubePlayer()
        } else {
          window.onYouTubeIframeAPIReady = initYoutubePlayer
        }
      } catch (err) {
        console.error("Không thể phát video YouTube", err)
        setError("Lỗi khi tải phương tiện truyền thông từ YouTube.")
      }
    }

    loadSongVideo()
  }, [playingSong])

  // Đồng bộ nút Phát / Tạm dừng trên giao diện Web với trình phát YouTube
  useEffect(() => {
    if (window.ytPlayerInstance && typeof window.ytPlayerInstance.playVideo === 'function') {
      if (isPlaying) {
        window.ytPlayerInstance.playVideo()
      } else {
        window.ytPlayerInstance.pauseVideo()
      }
    }
  }, [isPlaying])

  // Đồng bộ thanh âm lượng trên giao diện Web với trình phát YouTube
  useEffect(() => {
    if (window.ytPlayerInstance && typeof window.ytPlayerInstance.setVolume === 'function') {
      if (isMuted) {
        window.ytPlayerInstance.setVolume(0)
      } else {
        window.ytPlayerInstance.setVolume(volume)
      }
    }
  }, [volume, isMuted])

  // Chạy một đồng hồ đếm thời gian (Interval) để cập nhật thời gian đang phát hiện tại (giây, %) 
  // của video từ trình phát YouTube lên thanh tiến trình (progress bar) của giao diện Web cứ mỗi 500ms.
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
          // Bỏ qua lỗi nhỏ nếu iframe chưa render kịp
        }
      }, 500)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isPlaying])

  // Tải dữ liệu ban đầu khi ứng dụng khởi chạy (Bài hát phổ biến trang chủ và tài khoản demo Last.fm)
  useEffect(() => {
    let active = true
    async function loadInitialData() {
      try {
        const popResult = await searchSongs('')
        if (active) {
          setPopularSongs(popResult.slice(0, 8))
        }
      } catch (err) {
        console.error("Lỗi tải bài hát phổ biến ban đầu", err)
      }

      setUsersLoading(true)
      try {
        const usersResult = await getDemoUsers(DEMO_USER_LIMIT)
        if (active) {
          setDemoUsers(formatDemoUsers(usersResult))
        }
      } catch (err) {
        console.error("Lỗi tải danh sách người dùng demo", err)
      } finally {
        if (active) setUsersLoading(false)
      }
    }
    loadInitialData()
    return () => {
      active = false
    }
  }, [])

  // Xử lý ô Tìm kiếm bài hát tích hợp kỹ thuật Debounce (Chờ 250ms sau khi người dùng dừng gõ phím mới gọi API).
  // Việc này giúp tránh gửi hàng chục yêu cầu API vô ích lên máy chủ khi người dùng đang gõ nhanh.
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
          setError('Không thể kết nối tới máy chủ Spring Boot API.')
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

  // Xử lý hành động bấm nút phát / tạm dừng một bài hát
  function handlePlaySong(song) {
    if (playingSong?.trackId === song.trackId) {
      setIsPlaying(!isPlaying) // Bật/tắt nhạc nếu bài đang phát trùng với bài vừa click
    } else {
      setPlayingSong(song)     // Phát bài mới hoàn toàn
      setIsPlaying(true)
      setPlayProgress(0)
      setPlaySeconds(0)
    }
  }

  // Xử lý khi người dùng chọn 1 bài hát cụ thể để tìm các bài hát tương tự (Song Mode)
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
      // Tự động phát bài hát đó trên trình phát nhạc luôn
      setPlayingSong(song)
      setIsPlaying(true)
      setPlayProgress(0)
      setPlaySeconds(0)
    } catch (loadError) {
      setRecommendations([])
      setError('Không thể tải bài hát gợi ý.')
    } finally {
      setRecommendLoading(false)
    }
  }

  // Xử lý khi chọn một người bạn Last.fm để xem gu nhạc gợi ý cá nhân hóa của họ (User Mode)
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
      setError('Không thể tải danh sách gợi ý cá nhân hóa cho bạn bè.')
    } finally {
      setRecommendLoading(false)
    }
  }

  // Xử lý sự kiện đăng nhập tài khoản người dùng
  async function handleAuthLogin(e) {
    e.preventDefault()
    setAuthError('')
    try {
      const data = await apiLogin(authUsername, authPassword)
      setCurrentUser(data)
      // Đồng bộ danh sách like/dislike từ máy chủ về giao diện web
      if (data.likedSongIds) {
        setLikedSongIds(new Set(data.likedSongIds))
      }
      if (data.dislikedSongIds) {
        setDislikedSongIds(new Set(data.dislikedSongIds))
      }
      // Tải gợi ý riêng cho họ hiển thị trên trang chủ
      loadPersonalRecommendations(data.username)
      setAuthModalOpen(null)
      setAuthUsername('')
      setAuthPassword('')
    } catch (err) {
      setAuthError(err.message || 'Đăng nhập thất bại!')
    }
  }

  // Xử lý sự kiện đăng ký tài khoản mới
  async function handleAuthRegister(e) {
    e.preventDefault()
    setAuthError('')
    try {
      const data = await apiRegister(authUsername, authEmail, authPassword, authFullName)
      setCurrentUser(data)
      setLikedSongIds(new Set())
      setDislikedSongIds(new Set())
      setPersonalRecommendations([])
      setAuthModalOpen(null)
      setAuthUsername('')
      setAuthPassword('')
      setAuthEmail('')
      setAuthFullName('')
    } catch (err) {
      setAuthError(err.message || 'Đăng ký thất bại!')
    }
  }

  // Xử lý sự kiện đăng xuất tài khoản
  function handleLogout() {
    apiLogout()
    setCurrentUser(null)
    setLikedSongIds(new Set())
    setDislikedSongIds(new Set())
    setPersonalRecommendations([])
    setSelectedSong(null)
    setSelectedUser(null)
    setRecommendations([])
    setIsBlendMode(false)
  }

  // Xử lý tạo Playlist chung (Taste Blend Playlist) giữa bạn và người bạn Last.fm được chọn
  async function handleCreateBlend(user) {
    if (!currentUser) {
      setAuthError('Vui lòng đăng nhập để trộn gu nhạc (Taste Blend) cùng bạn bè!')
      setAuthModalOpen('login')
      return
    }
    setIsBlendMode(true)
    setSelectedUser(user)
    setSelectedSong(null)
    setRecommendLoading(true)
    setError('')
    try {
      const result = await getBlendRecommendations(currentUser.username, user.userId)
      setRecommendations(result.recommendations || [])
      setBlendMatchScore(result.match_score ?? 0.5)
    } catch (loadError) {
      setRecommendations([])
      setError('Không thể tải danh sách gợi ý kết hợp (Blend).')
    } finally {
      setRecommendLoading(false)
    }
  }

  // Xử lý hành động Like hoặc Dislike một bài hát (Cơ chế phản hồi thời gian thực - Real-time Feedback Loop).
  // Khi người dùng like/dislike, hệ thống lưu xuống cơ sở dữ liệu Spring Boot, đồng bộ sang mô hình AI FastAPI,
  // sau đó lập tức truy vấn lại danh sách gợi ý mới nhất loại bỏ các bài hát bị ghét và bổ sung bài mới.
  async function handleFeedback(song, type) {
    if (!currentUser) {
      setAuthError('Vui lòng đăng nhập để thể hiện sở thích âm nhạc của bạn!')
      setAuthModalOpen('login')
      return
    }
    
    const userId = currentUser.username
    const trackId = song.trackId

    try {
      // Gọi API gửi lượt phản hồi (LIKE hoặc DISLIKE) lên backend Spring Boot
      await submitFeedback(userId, trackId, type)
      
      // Tạo bản sao mới của các Set để React nhận diện được sự thay đổi trạng thái và cập nhật lại giao diện
      const updatedLikes = new Set(likedSongIds)
      const updatedDislikes = new Set(dislikedSongIds)
      
      if (type === 'LIKE') {
        if (updatedLikes.has(trackId)) {
          updatedLikes.delete(trackId) // Bỏ thích nếu click lại vào nút thích
        } else {
          updatedLikes.add(trackId)
          updatedDislikes.delete(trackId) // Nếu đang ghét mà chuyển sang thích thì xóa khỏi danh sách ghét
        }
      } else {
        // Hành động DISLIKE
        if (updatedDislikes.has(trackId)) {
          updatedDislikes.delete(trackId) // Bỏ ghét nếu click lại vào nút ghét
        } else {
          updatedDislikes.add(trackId)
          updatedLikes.delete(trackId) // Nếu đang thích mà bấm ghét thì xóa khỏi danh sách thích
        }
      }
      setLikedSongIds(updatedLikes)
      setDislikedSongIds(updatedDislikes)

      // Tải lại danh sách 8 bài gợi ý Made For You ở trang chủ
      loadPersonalRecommendations(userId)

      // Đồng thời chạy lại truy vấn gợi ý ở màn hình chính (nếu đang xem dở) để bài hát bị dislike biến mất lập tức
      if (isBlendMode && selectedUser) {
        const result = await getBlendRecommendations(userId, selectedUser.userId)
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
      console.error("Gửi phản hồi thất bại", err)
      setError("Không thể ghi nhận phản hồi âm nhạc.")
    }
  }

  // Reset toàn bộ gu nhạc của tài khoản hiện tại về trạng thái ban đầu (Xóa hết likes/dislikes)
  async function handleResetFeedback() {
    if (!currentUser) {
      setAuthError('Vui lòng đăng nhập để quản lý tùy chọn sở thích.')
      setAuthModalOpen('login')
      return
    }
    const userId = currentUser.username
    try {
      await resetFeedback(userId)
      // Làm trống các State cục bộ ở frontend
      setLikedSongIds(new Set())
      setDislikedSongIds(new Set())
      setPersonalRecommendations([])
      setError('')
      
      // Tải lại dữ liệu gợi ý rỗng/mặc định sau khi reset
      if (isBlendMode && selectedUser) {
        const result = await getBlendRecommendations(userId, selectedUser.userId)
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
      console.error("Reset gu nhạc thất bại", err)
    }
  }

  // --- 2. CÁC HÀM TÍNH TOÁN TỐI ƯU HÓA (useMemo) ---
  // useMemo giúp ghi nhớ kết quả tính toán và chỉ tính lại khi một trong các dependency thay đổi.
  // Tránh việc bộ lọc chạy lại mỗi khi người dùng click linh tinh hoặc tăng giảm âm lượng.

  // visibleDemoUsers: Danh sách bạn bè được hiển thị sau khi lọc qua từ khóa tìm kiếm bạn bè (userQuery)
  const visibleDemoUsers = useMemo(() => {
    const normalizedQuery = userQuery.trim().toLowerCase()
    if (!normalizedQuery) return demoUsers

    return demoUsers.filter((user) => {
      // Tìm kiếm bạn bè qua: tên hiển thị, ID Last.fm hoặc tên các ca sĩ/nghệ sĩ họ thích nghe nhất
      const searchableProfile = [
        user.displayName,
        user.userId,
        user.shortId,
        ...(user.topArtists ?? []),
      ].join(' ').toLowerCase()

      return searchableProfile.includes(normalizedQuery)
    })
  }, [demoUsers, userQuery]) // Chỉ tính toán lại khi danh sách demoUsers hoặc từ khóa userQuery thay đổi

  // mockAudioFeatures: Tự động giả lập 5 thông số âm thanh (Acoustic Signature) cho bài hát đang chọn/phát.
  // Phân tích các thông số: Danceability (Độ dễ nhảy), Energy (Năng lượng), Valence (Tâm trạng tích cực), 
  // Acousticness (Độ mộc mạc), Tempo (Nhịp điệu BPM).
  // Được giả lập bằng mã băm (hash) của trackId để đảm bảo bài hát đó khi tải lại thì các chỉ số vẫn giữ nguyên.
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
  }, [selectedSong, playingSong]) // Chỉ tính toán lại khi bài hát đang chọn hoặc đang phát thay đổi

  // Hàm phụ trợ định dạng thời gian giây thành định dạng MM:SS để hiển thị thời gian bài hát phát.
  // Ví dụ: 125 giây -> "2:05"
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

        {currentUser ? (
          <div className="sidebar-user-panel">
            <div className="user-info-brief">
              <div className="user-avatar-small">
                {currentUser.fullName ? currentUser.fullName.charAt(0).toUpperCase() : currentUser.username.charAt(0).toUpperCase()}
              </div>
              <div className="user-text-brief">
                <span className="user-username-badge">{currentUser.fullName || currentUser.username}</span>
                <span className="user-role-badge">Member</span>
              </div>
            </div>
            <button 
              type="button" 
              className="logout-btn-icon" 
              title="Logout"
              onClick={handleLogout}
            >
              🚪
            </button>
          </div>
        ) : (
          <div style={{ padding: '0 8px', margin: '10px 0' }}>
            <button 
              type="button" 
              className="login-prompt-sidebar-btn"
              onClick={() => {
                setAuthError('')
                setAuthModalOpen('login')
              }}
            >
              👤 Sign In to Like
            </button>
          </div>
        )}

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
              {currentUser && (
                <section className="dashboard-section animate-fade-in">
                  <h2>Made For {currentUser.fullName || currentUser.username}</h2>
                  {recommendLoading && <p className="loading-text">Generating recommendations...</p>}
                  {personalRecommendations.length > 0 ? (
                    <div className="premium-grid">
                      {personalRecommendations.map((song) => (
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
                  ) : (
                    !recommendLoading && <p className="empty-state">Like some songs to get personalized recommendations here!</p>
                  )}
                </section>
              )}

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
                          <tr 
                            key={song.trackId} 
                            onClick={() => {
                              if (!dislikedSongIds.has(song.trackId)) handleSelectSong(song)
                            }} 
                            className={`${selectedSong?.trackId === song.trackId ? 'selected-row' : ''} ${dislikedSongIds.has(song.trackId) ? 'disliked-row' : ''}`}
                          >
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
                                  title="Like this song"
                                  onClick={() => handleFeedback(song, 'LIKE')}
                                >
                                  💚
                                </button>
                                <button 
                                  type="button" 
                                  className={`action-btn-dislike ${dislikedSongIds.has(song.trackId) ? 'active' : ''}`}
                                  title="Dislike this song"
                                  onClick={() => handleFeedback(song, 'DISLIKE')}
                                >
                                  {dislikedSongIds.has(song.trackId) ? '🚫' : '👎'}
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
                          {recommendations.filter(item => !dislikedSongIds.has(item.trackId)).map((item, index) => {
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
                title="Like"
                onClick={() => handleFeedback(playingSong, 'LIKE')}
              >
                {likedSongIds.has(playingSong.trackId) ? '💚' : '♡'}
              </button>
              <button 
                type="button" 
                className={`player-dislike-btn ${dislikedSongIds.has(playingSong.trackId) ? 'active' : ''}`}
                title="Dislike"
                onClick={() => handleFeedback(playingSong, 'DISLIKE')}
              >
                {dislikedSongIds.has(playingSong.trackId) ? '🚫' : '👎'}
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

      {/* 4. AUTH MODAL */}
      {authModalOpen && (
        <div className="modal-overlay" onClick={() => setAuthModalOpen(null)}>
          <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
            <button 
              type="button" 
              className="auth-modal-close"
              onClick={() => setAuthModalOpen(null)}
            >
              ✕
            </button>
            
            <h2>{authModalOpen === 'login' ? 'Sign In' : 'Create Account'}</h2>
            
            {authError && <p className="auth-error-msg">{authError}</p>}
            
            <form onSubmit={authModalOpen === 'login' ? handleAuthLogin : handleAuthRegister} className="auth-form">
              <div className="form-group">
                <label>Username</label>
                <input 
                  type="text" 
                  required
                  value={authUsername}
                  onChange={(e) => setAuthUsername(e.target.value)}
                  placeholder="Enter username"
                />
              </div>
              
              {authModalOpen === 'register' && (
                <>
                  <div className="form-group">
                    <label>Email Address</label>
                    <input 
                      type="email" 
                      required
                      value={authEmail}
                      onChange={(e) => setAuthEmail(e.target.value)}
                      placeholder="Enter email"
                    />
                  </div>
                  <div className="form-group">
                    <label>Full Name</label>
                    <input 
                      type="text" 
                      value={authFullName}
                      onChange={(e) => setAuthFullName(e.target.value)}
                      placeholder="Enter full name"
                    />
                  </div>
                </>
              )}
              
              <div className="form-group">
                <label>Password</label>
                <input 
                  type="password" 
                  required
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </div>
              
              <button type="submit" className="auth-submit-btn">
                {authModalOpen === 'login' ? 'Sign In' : 'Sign Up'}
              </button>
            </form>
            
            <p className="auth-toggle-text">
              {authModalOpen === 'login' ? "Don't have an account?" : "Already have an account?"}
              <button 
                type="button" 
                className="auth-toggle-link"
                onClick={() => {
                  setAuthError('')
                  setAuthModalOpen(authModalOpen === 'login' ? 'register' : 'login')
                }}
              >
                {authModalOpen === 'login' ? 'Sign Up' : 'Sign In'}
              </button>
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
