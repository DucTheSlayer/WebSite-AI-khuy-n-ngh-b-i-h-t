package com.example.musicrecommender.controller;

import com.example.musicrecommender.dto.RecommendationDto;
import com.example.musicrecommender.dto.UserProfileDto;
import com.example.musicrecommender.entity.Song;
import com.example.musicrecommender.entity.User;
import com.example.musicrecommender.entity.UserFeedback;
import com.example.musicrecommender.repository.UserRepository;
import com.example.musicrecommender.repository.UserFeedbackRepository;
import com.example.musicrecommender.service.AiRecommendationService;
import com.example.musicrecommender.service.SongService;
import com.example.musicrecommender.dto.FeedbackRequestDto;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Controller chịu trách nhiệm định nghĩa các API liên quan đến bài hát và gợi ý âm nhạc.
 * @RestController: Đánh dấu đây là một Controller cung cấp API dạng REST (trả về dữ liệu JSON).
 */
@RestController
public class SongController {

    // Khai báo các Service và Repository cần sử dụng (áp dụng nguyên lý Dependency Injection)
    private final SongService songService;
    private final AiRecommendationService aiRecommendationService;
    private final UserRepository userRepository;
    private final UserFeedbackRepository userFeedbackRepository;

    /**
     * @Autowired: Tự động nhúng (Inject) các Beans vào Constructor của Controller.
     */
    @Autowired
    public SongController(
            SongService songService,
            AiRecommendationService aiRecommendationService,
            UserRepository userRepository,
            UserFeedbackRepository userFeedbackRepository
    ) {
        this.songService = songService;
        this.aiRecommendationService = aiRecommendationService;
        this.userRepository = userRepository;
        this.userFeedbackRepository = userFeedbackRepository;
    }

    /**
     * API Tìm kiếm / Lấy danh sách bài hát.
     * GET: http://localhost:8080/api/songs?q=keyword
     */
    @GetMapping("/api/songs")
    public List<Song> allSongs(@RequestParam(required = false) String q) {
        if (q != null) {
            return songService.searchSongs(q); // Tìm bài hát theo từ khóa tìm kiếm (tên bài hát, ca sĩ)
        }
        return songService.findAll(); // Trả về toàn bộ danh sách bài hát nếu không truyền tham số q
    }

    /**
     * API Lấy chi tiết bài hát theo ID.
     * GET: http://localhost:8080/api/songs/track_id_xyz
     */
    @GetMapping({"/api/song/{id}", "/api/songs/{id}"})
    public Song getSong(@PathVariable String id) {
        return songService.findById(id).orElse(null);
    }

    /**
     * API Gợi ý danh sách bài hát tương tự theo một bài hát nguồn.
     * GET: http://localhost:8080/api/recommend/track_id_xyz?topN=10
     */
    @GetMapping("/api/recommend/{trackId}")
    public List<RecommendationDto> recommendByTrack(
        @PathVariable String trackId,
        @RequestParam(defaultValue = "10") int topN
    ) {
        // Trích xuất username của người dùng đang đăng nhập từ Security Context (JWT Token)
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        // Nếu chưa đăng nhập, Spring Security sẽ gán tên mặc định là "anonymousUser"
        String userId = "anonymousUser".equals(username) ? null : username;
        
        // Gọi AI Service xử lý, truyền thêm userId để AI lọc bỏ các bài hát người dùng này đã bấm Dislike
        return aiRecommendationService.recommendByTrack(trackId, topN, userId);
    }

    /**
     * API Gợi ý cá nhân hóa dựa trên tên người dùng.
     * GET: http://localhost:8080/api/recommend/user/username_xyz?topN=10
     */
    @GetMapping("/api/recommend/user/{userId}")
    public List<RecommendationDto> recommendByUser(
        @PathVariable String userId,
        @RequestParam(defaultValue = "10") int topN
    ) {
        return aiRecommendationService.recommendByUser(userId, topN);
    }

    /**
     * API Lấy danh sách các demo người dùng Last.fm để phục vụ demo học thuật.
     */
    @GetMapping("/api/users/demo")
    public List<UserProfileDto> demoUsers(@RequestParam(defaultValue = "12") int limit) {
        return aiRecommendationService.getDemoUsers(limit);
    }

    /**
     * API Lấy danh sách bài hát phổ biến nhất.
     */
    @GetMapping("/api/popular")
    public List<Song> popularSongs(@RequestParam(defaultValue = "10") int limit) {
        return songService.findTopPopular(limit);
    }

    @GetMapping("/")
    public String home() {
        return "API dang chay. Dung /api/songs, /api/songs/{id}, /api/recommend/{trackId}";
    }

    /**
     * API Ghi nhận hành động phản hồi (Like/Dislike) bài hát của người dùng.
     * POST: http://localhost:8080/api/feedback
     * @Transactional: Đảm bảo tính nhất quán dữ liệu (Rollback nếu xảy ra lỗi trong quá trình lưu DB).
     */
    @PostMapping("/api/feedback")
    @Transactional
    public ResponseEntity<?> submitFeedback(@RequestBody FeedbackRequestDto request) {
        try {
            // Lấy username từ Security Context của người dùng đang gọi API
            String username = SecurityContextHolder.getContext().getAuthentication().getName();
            User user = userRepository.findByUsername(username)
                    .orElseThrow(() -> new IllegalArgumentException("User not found"));

            Song song = songService.findById(request.getTrackId())
                    .orElseThrow(() -> new IllegalArgumentException("Song not found"));

            // Kiểm tra xem lượt tương tác này đã tồn tại trong DB chưa, nếu chưa thì tạo mới
            UserFeedback feedback = userFeedbackRepository.findByUserAndSong(user, song)
                    .orElse(new UserFeedback());
            
            feedback.setUser(user);
            feedback.setSong(song);
            feedback.setFeedbackType(request.getFeedbackType());

            // Lưu phản hồi xuống MySQL Database
            userFeedbackRepository.save(feedback);

            // Gửi thông tin phản hồi sang Python FastAPI service để cập nhật model AI
            aiRecommendationService.submitFeedback(
                username,
                request.getTrackId(),
                request.getFeedbackType()
            );

            return ResponseEntity.ok().body(java.util.Map.of("status", "success"));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(java.util.Map.of("error", e.getMessage()));
        }
    }

    /**
     * API Reset toàn bộ gu nhạc (Xóa tất cả lượt Like/Dislike của tài khoản).
     * POST: http://localhost:8080/api/feedback/reset/username_xyz
     */
    @PostMapping("/api/feedback/reset/{userId}")
    @Transactional
    public ResponseEntity<?> resetFeedback(@PathVariable String userId) {
        try {
            // Xác minh người dùng chỉ được phép xóa lịch sử của chính họ (tránh xóa hộ người khác)
            String username = SecurityContextHolder.getContext().getAuthentication().getName();
            if (!username.equals(userId)) {
                return ResponseEntity.status(403).body(java.util.Map.of("error", "Forbidden"));
            }

            User user = userRepository.findByUsername(username)
                    .orElseThrow(() -> new IllegalArgumentException("User not found"));

            // Xóa tất cả các hàng dữ liệu phản hồi của User này trong MySQL
            userFeedbackRepository.deleteByUser(user);

            // Thông báo sang Python FastAPI để xóa lịch sử tương thích của User
            aiRecommendationService.resetFeedback(username);

            return ResponseEntity.ok().body(java.util.Map.of("status", "success"));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(java.util.Map.of("error", e.getMessage()));
        }
    }

    /**
     * API Tìm kiếm MV bài hát trên YouTube.
     */
    @GetMapping("/api/youtube/search")
    public ResponseEntity<?> searchYoutube(@RequestParam String q) {
        try {
            String videoId = aiRecommendationService.searchYoutube(q);
            return ResponseEntity.ok().body(java.util.Map.of("video_id", videoId));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(java.util.Map.of("error", e.getMessage()));
        }
    }

    /**
     * API Gợi ý kết hợp gu nhạc cho 2 người (Taste Blend).
     */
    @GetMapping("/api/recommend/blend")
    public ResponseEntity<?> recommendBlend(
        @RequestParam String user1,
        @RequestParam String user2,
        @RequestParam(defaultValue = "10") int topN
    ) {
        try {
            Object result = aiRecommendationService.recommendBlend(user1, user2, topN);
            return ResponseEntity.ok().body(result);
        } catch (Exception e) {
            return ResponseEntity.status(500).body(java.util.Map.of("error", e.getMessage()));
        }
    }
}
