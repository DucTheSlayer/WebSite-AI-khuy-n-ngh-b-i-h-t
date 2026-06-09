package com.example.musicrecommender.controller;

import com.example.musicrecommender.config.JwtUtils;
import com.example.musicrecommender.dto.AuthResponseDto;
import com.example.musicrecommender.dto.LoginRequestDto;
import com.example.musicrecommender.dto.RegisterRequestDto;
import com.example.musicrecommender.entity.User;
import com.example.musicrecommender.entity.UserFeedback;
import com.example.musicrecommender.repository.UserRepository;
import com.example.musicrecommender.repository.UserFeedbackRepository;
import com.example.musicrecommender.service.AiRecommendationService;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Controller chịu trách nhiệm xử lý các API liên quan đến xác thực người dùng (Đăng ký, Đăng nhập, Xem thông tin cá nhân).
 * @RestController: Đánh dấu đây là một controller của Spring REST, trả về dữ liệu dạng JSON.
 * @RequestMapping("/api/auth"): Định nghĩa tiền tố đường dẫn chung cho toàn bộ các endpoint trong Class này.
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    // Khai báo các Dependencies cần dùng (Spring Boot sẽ tự động truyền qua Constructor Injection)
    private final AuthenticationManager authenticationManager;
    private final UserRepository userRepository;
    private final UserFeedbackRepository userFeedbackRepository;
    private final PasswordEncoder encoder;
    private final JwtUtils jwtUtils;
    private final AiRecommendationService aiRecommendationService;

    public AuthController(
            AuthenticationManager authenticationManager,
            UserRepository userRepository,
            UserFeedbackRepository userFeedbackRepository,
            PasswordEncoder encoder,
            JwtUtils jwtUtils,
            AiRecommendationService aiRecommendationService
    ) {
        this.authenticationManager = authenticationManager;
        this.userRepository = userRepository;
        this.userFeedbackRepository = userFeedbackRepository;
        this.encoder = encoder;
        this.jwtUtils = jwtUtils;
        this.aiRecommendationService = aiRecommendationService;
    }

    /**
     * API Đăng ký tài khoản mới.
     * POST: http://localhost:8080/api/auth/register
     * 
     * @param registerRequest Đối tượng DTO chứa dữ liệu đăng ký (username, email, password, fullName) gửi từ client
     * @return ResponseEntity Trả về thông tin user kèm theo JWT Token nếu đăng ký thành công
     */
    @PostMapping("/register")
    public ResponseEntity<?> registerUser(@RequestBody RegisterRequestDto registerRequest) {
        // 1. Kiểm tra xem tên đăng nhập đã được sử dụng chưa
        if (userRepository.existsByUsername(registerRequest.getUsername())) {
            return ResponseEntity.badRequest().body(Map.of("message", "Error: Username is already taken!"));
        }

        // 2. Kiểm tra xem email đã được sử dụng chưa
        if (userRepository.existsByEmail(registerRequest.getEmail())) {
            return ResponseEntity.badRequest().body(Map.of("message", "Error: Email is already in use!"));
        }

        // 3. Khởi tạo thực thể User mới và mã hóa mật khẩu bằng BCrypt
        User user = new User();
        user.setUsername(registerRequest.getUsername());
        user.setEmail(registerRequest.getEmail());
        // Bắt buộc phải mã hóa mật khẩu, không được lưu plaintext để đảm bảo an toàn thông tin
        user.setPasswordHash(encoder.encode(registerRequest.getPassword()));
        user.setFullName(registerRequest.getFullName());

        // Lưu thông tin người dùng vào cơ sở dữ liệu MySQL
        userRepository.save(user);

        // 4. Tạo JWT Token tự động để đăng nhập ngay sau khi đăng ký thành công
        String jwt = jwtUtils.generateJwtToken(user.getUsername());

        return ResponseEntity.ok(new AuthResponseDto(
                jwt,
                user.getUsername(),
                user.getEmail(),
                user.getFullName(),
                new ArrayList<>(), // Tài khoản mới chưa có lịch sử like
                new ArrayList<>()  // Tài khoản mới chưa có lịch sử dislike
        ));
    }

    /**
     * API Đăng nhập tài khoản.
     * POST: http://localhost:8080/api/auth/login
     * 
     * @param loginRequest Đối tượng DTO chứa (username, password) gửi từ client
     * @return ResponseEntity Trả về JWT Token, thông tin cá nhân và danh sách bài hát đã like/dislike
     */
    @PostMapping("/login")
    public ResponseEntity<?> authenticateUser(@RequestBody LoginRequestDto loginRequest) {
        // 1. Xác thực thông tin đăng nhập (username và password) thông qua AuthenticationManager của Spring Security.
        // Nếu thông tin sai, Spring Security sẽ tự động ném ra ngoại lệ AuthenticationException và trả về mã lỗi 401 Unauthorized.
        Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(loginRequest.getUsername(), loginRequest.getPassword()));

        // 2. Nếu xác thực thành công, lưu thông tin xác thực vào Security Context của Spring
        SecurityContextHolder.getContext().setAuthentication(authentication);
        
        // 3. Tạo chuỗi mã hóa JWT Token từ username để gửi về cho client
        String jwt = jwtUtils.generateJwtToken(loginRequest.getUsername());

        // 4. Tìm kiếm thông tin người dùng trong DB
        User user = userRepository.findByUsername(loginRequest.getUsername()).orElseThrow();

        // 5. Truy vấn lịch sử phản hồi nhạc (Likes/Dislikes) của user này từ DB MySQL
        List<UserFeedback> feedbacks = userFeedbackRepository.findByUser(user);
        List<String> likedSongIds = feedbacks.stream()
                .filter(fb -> "LIKE".equalsIgnoreCase(fb.getFeedbackType()))
                .map(fb -> fb.getSong().getTrackId())
                .collect(Collectors.toList());

        List<String> dislikedSongIds = feedbacks.stream()
                .filter(fb -> "DISLIKE".equalsIgnoreCase(fb.getFeedbackType()))
                .map(fb -> fb.getSong().getTrackId())
                .collect(Collectors.toList());

        // 6. Đồng bộ toàn bộ lịch sử phản hồi nhạc của tài khoản này sang Python FastAPI AI service.
        // Việc này đảm bảo mô hình AI in-memory được đồng bộ hóa tức thời với lịch sử trong MySQL của tài khoản.
        aiRecommendationService.syncUserFeedback(user.getUsername(), feedbacks);

        // 7. Trả dữ liệu xác thực về cho Client để lưu trữ trong localStorage
        return ResponseEntity.ok(new AuthResponseDto(
                jwt,
                user.getUsername(),
                user.getEmail(),
                user.getFullName(),
                likedSongIds,
                dislikedSongIds
        ));
    }

    /**
     * API Lấy thông tin tài khoản hiện tại từ JWT Token gửi kèm ở tiêu đề request (Authorization Header).
     * GET: http://localhost:8080/api/auth/me
     */
    @GetMapping("/me")
    public ResponseEntity<?> getCurrentUser() {
        // 1. Lấy thông tin xác thực hiện tại từ Security Context (đã được cấu hình ở bộ lọc JwtAuthTokenFilter)
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated() || "anonymousUser".equals(authentication.getPrincipal())) {
            return ResponseEntity.status(401).body(Map.of("message", "Unauthorized"));
        }

        // Lấy username từ token hợp lệ
        String username = authentication.getName();
        User user = userRepository.findByUsername(username)
                .orElse(null);
        if (user == null) {
            return ResponseEntity.status(404).body(Map.of("message", "User not found"));
        }

        // 2. Lấy danh sách ID các bài hát đã tương tác (Like/Dislike)
        List<UserFeedback> feedbacks = userFeedbackRepository.findByUser(user);
        List<String> likedSongIds = feedbacks.stream()
                .filter(fb -> "LIKE".equalsIgnoreCase(fb.getFeedbackType()))
                .map(fb -> fb.getSong().getTrackId())
                .collect(Collectors.toList());

        List<String> dislikedSongIds = feedbacks.stream()
                .filter(fb -> "DISLIKE".equalsIgnoreCase(fb.getFeedbackType()))
                .map(fb -> fb.getSong().getTrackId())
                .collect(Collectors.toList());

        // 3. Trả về thông tin tài khoản
        return ResponseEntity.ok(Map.of(
                "username", user.getUsername(),
                "email", user.getEmail(),
                "fullName", user.getFullName() != null ? user.getFullName() : "",
                "likedSongIds", likedSongIds,
                "dislikedSongIds", dislikedSongIds
        ));
    }
}
