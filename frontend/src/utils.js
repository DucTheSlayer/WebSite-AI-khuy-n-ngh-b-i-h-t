/**
 * File helpers và utilities cho ứng dụng React (SpotiAI Frontend)
 * File này chứa các hàm phụ trợ độc lập, không chứa state của React, giúp code ở App.jsx gọn gàng hơn.
 */

// Danh sách tên hiển thị giả lập cho các user demo (Last.fm)
export const FRIEND_NAMES = [
  'Alex Mercer', 'Sarah Connor', 'Bruce Wayne', 'Clark Kent',
  'Peter Parker', 'Selina Kyle', 'Tony Stark', 'Natasha Romanoff',
  'Steve Rogers', 'Wanda Maximoff', 'Luke Skywalker', 'Leia Organa',
  'Han Solo', 'Frodo Baggins', 'Samwise Gamgee', 'Harry Potter',
  'Hermione Granger', 'Ron Weasley', 'Sherlock Holmes', 'John Watson',
  'Michael Scott', 'Jessica Alba', 'David Miller', 'Emily Watson'
];

/**
 * Hàm làm sạch các ký tự bị lỗi font / giải mã sai Encoding UTF-8 từ API (ví dụ các chữ có dấu đặc biệt).
 * Sử dụng TextDecoder để giải mã lại chuỗi byte gốc.
 * 
 * @param {string} value Chuỗi đầu vào cần làm sạch
 * @returns {string} Chuỗi sau khi được sửa lỗi font
 */
export function cleanDisplayText(value = '') {
  if (!/[ÃÂâ]/.test(value)) {
    return value;
  }
  try {
    const bytes = Uint8Array.from([...value].map((character) => character.charCodeAt(0) & 255));
    return new TextDecoder('utf-8').decode(bytes);
  } catch {
    return value;
  }
}

/**
 * Hàm chuẩn hóa và định dạng dữ liệu các Demo Users từ hệ thống gợi ý.
 * Gán ngẫu nhiên trạng thái nghe nhạc (Offline, Online, đang nghe bài của nghệ sĩ nào đó)
 * dựa trên mã hash của userId để đảm bảo tính nhất quán (mỗi lần tải lại thì trạng thái vẫn giữ nguyên theo user đó).
 * 
 * @param {Array} users Danh sách user thô nhận về từ API
 * @returns {Array} Danh sách user đã định dạng, có đầy đủ tên hiển thị, avatar và trạng thái nghe nhạc
 */
export function formatDemoUsers(users) {
  return [...users]
    .sort((left, right) => (right.interactions ?? 0) - (left.interactions ?? 0))
    .map((user, index) => {
      const displayName = FRIEND_NAMES[index % FRIEND_NAMES.length] || `Friend ${index + 1}`;
      const topArtists = (user.topArtists ?? []).map(cleanDisplayText).filter(Boolean);
      
      // Tạo một mã băm (hash) đơn giản từ userId để tạo trạng thái nghe nhạc cố định cho user đó
      let hash = 0;
      const uid = user.userId || '';
      for (let i = 0; i < uid.length; i++) {
        hash = uid.charCodeAt(i) + ((hash << 5) - hash);
      }
      
      const isOnline = Math.abs(hash) % 10 < 8; // 80% cơ hội online
      let listeningStatus = 'Offline';
      if (isOnline && topArtists.length > 0) {
        const artistIdx = Math.abs(hash * 31) % topArtists.length;
        listeningStatus = `Listening to ${topArtists[artistIdx]}`;
      } else if (isOnline) {
        listeningStatus = 'Online';
      }

      return {
        ...user,
        displayName,
        listeningStatus,
        shortId: user.userId?.slice(0, 10) ?? '',
        topArtists,
      };
    });
}

/**
 * Hàm tự động tạo style CSS Gradient cho bìa album bài hát (mock cover) dựa vào trackId của bài hát.
 * Thuật toán băm (hash) trackId thành góc xoay và các tông màu HSL phù hợp, giúp mỗi bài hát
 * có một hình bìa Gradient rực rỡ và duy nhất, không trùng lặp mà không cần tải ảnh thật.
 * 
 * @param {string} trackId ID của bài hát làm chuỗi băm gốc
 * @param {string} title Tiêu đề bài hát (dùng làm fallback)
 * @returns {object} Object chứa CSS Style dùng cho thuộc tính style={{...}} của React
 */
export function getMockCoverStyle(trackId, title = 'Song') {
  if (!trackId) return { background: 'linear-gradient(135deg, #282828, #121212)' };
  let hash = 0;
  for (let i = 0; i < trackId.length; i++) {
    hash = trackId.charCodeAt(i) + ((hash << 5) - hash);
  }
  const h1 = Math.abs(hash) % 360;
  const h2 = Math.abs(hash * 31) % 360;
  // HSL màu sáng và tối kết hợp để tạo ra gradient sâu và đẹp mắt
  const c1 = `hsl(${h1}, 70%, 45%)`;
  const c2 = `hsl(${h2}, 80%, 20%)`;
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
  };
}

/**
 * Hàm lấy chữ cái đầu tiên của bài hát để vẽ lên bìa album.
 * 
 * @param {string} title Tên bài hát
 * @returns {string} Chữ cái đầu tiên viết hoa
 */
export function getFirstLetter(title) {
  return String(title || 'S').trim().charAt(0).toUpperCase();
}
