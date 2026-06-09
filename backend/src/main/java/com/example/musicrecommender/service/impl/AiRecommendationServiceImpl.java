package com.example.musicrecommender.service.impl;

import com.example.musicrecommender.dto.RecommendationDto;
import com.example.musicrecommender.dto.UserProfileDto;
import com.example.musicrecommender.entity.Song;
import com.example.musicrecommender.service.AiRecommendationService;
import com.example.musicrecommender.service.SongService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * Lớp triển khai thực tế của AiRecommendationService.
 * Chịu trách nhiệm thực hiện các cuộc gọi HTTP kết nối từ Spring Boot (Backend) sang FastAPI (AI Service)
 * để lấy danh sách gợi ý âm nhạc, tìm kiếm video Youtube, trộn gu nhạc Blend và đồng bộ hóa tương tác.
 * 
 * @Service: Đánh dấu đây là một Spring Bean thuộc tầng Service.
 */
@Service
public class AiRecommendationServiceImpl implements AiRecommendationService {

    private final SongService songService;
    private final ObjectMapper objectMapper; // Dùng để chuyển đổi (Parse) chuỗi JSON nhận về thành đối tượng Java
    private final HttpClient httpClient;     // Sử dụng HttpClient của Java 11+ để gửi HTTP Request
    private final String aiBaseUrl;           // URL gốc của FastAPI AI Service (mặc định http://localhost:8000)
    private final int topPopularFallback;     // Số bài hát phổ biến tối đa dùng làm dự phòng nếu AI gặp sự cố

    /**
     * Constructor Injection để nhúng các Bean và cấu hình.
     * @Value: Tiêm các cấu hình định nghĩa trong file application.properties vào biến.
     */
    public AiRecommendationServiceImpl(
        SongService songService,
        ObjectMapper objectMapper,
        @Value("${ai.service.base-url:http://localhost:8000}") String aiBaseUrl,
        @Value("${ai.service.timeout-seconds:3}") long timeoutSeconds,
        @Value("${ai.service.fallback-popular-size:10}") int topPopularFallback
    ) {
        this.songService = songService;
        this.objectMapper = objectMapper;
        this.aiBaseUrl = aiBaseUrl;
        this.topPopularFallback = topPopularFallback;
        // Khởi tạo đối tượng HttpClient kèm theo thời gian chờ kết nối tối đa (Timeout) để tránh bị treo luồng hệ thống
        this.httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(timeoutSeconds))
            .build();
    }

    /**
     * Gợi ý bài hát tương đồng dựa trên bài hát nguồn.
     * 
     * @param trackId ID của bài hát gốc
     * @param topN Số lượng gợi ý mong muốn
     * @param userId Username của người dùng đang đăng nhập (để lọc bỏ các bài đã Dislike)
     * @return List DTO danh sách bài gợi ý
     */
    @Override
    public List<RecommendationDto> recommendByTrack(String trackId, int topN, String userId) {
        try {
            // Mã hóa URL của trackId để tránh lỗi ký tự đặc biệt
            String encodedTrackId = URLEncoder.encode(trackId, StandardCharsets.UTF_8);
            String path = "/recommend/" + encodedTrackId + "?top_n=" + topN;
            if (userId != null && !userId.isBlank()) {
                path += "&user_id=" + URLEncoder.encode(userId, StandardCharsets.UTF_8);
            }
            return fetchRecommendations(path);
        } catch (Exception ignored) {
            // Nếu FastAPI bị lỗi kết nối hoặc sập, kích hoạt cơ chế dự phòng (Fallback)
            // Trả về danh sách bài hát phổ biến nhất để giao diện web không bị trống trơn
        }

        return fallbackPopularRecommendations(Math.min(topN, topPopularFallback));
    }

    /**
     * Gợi ý cá nhân hóa dựa trên tên người dùng.
     */
    @Override
    public List<RecommendationDto> recommendByUser(String userId, int topN) {
        try {
            String encodedUserId = URLEncoder.encode(userId, StandardCharsets.UTF_8);
            return fetchRecommendations("/recommend/user/" + encodedUserId + "?top_n=" + topN);
        } catch (Exception ignored) {
            // Kích hoạt Fallback
        }

        return fallbackPopularRecommendations(Math.min(topN, topPopularFallback));
    }

    /**
     * Lấy danh sách các tài khoản Last.fm giả lập để demo tính năng.
     */
    @Override
    public List<UserProfileDto> getDemoUsers(int limit) {
        try {
            URI uri = URI.create(aiBaseUrl + "/users/demo?limit=" + limit);
            HttpRequest request = HttpRequest.newBuilder(uri)
                .timeout(Duration.ofSeconds(3))
                .GET()
                .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 200 && response.statusCode() < 300) {
                return parseDemoUsers(response.body());
            }
        } catch (Exception ignored) {
        }

        return List.of();
    }

    /**
     * Hàm nội bộ gửi yêu cầu GET lên AI Service và trả về danh sách bài gợi ý đã được parse.
     */
    private List<RecommendationDto> fetchRecommendations(String pathAndQuery) throws Exception {
        URI uri = URI.create(aiBaseUrl + pathAndQuery);
        HttpRequest request = HttpRequest.newBuilder(uri)
            .timeout(Duration.ofSeconds(3))
            .GET()
            .build();

        // Thực hiện gửi request đồng bộ (Synchronous) và nhận về chuỗi Body JSON
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() >= 200 && response.statusCode() < 300) {
            return parseRecommendations(response.body());
        }

        throw new IllegalStateException("AI service returned status " + response.statusCode());
    }

    /**
     * Giải mã chuỗi JSON kết quả gợi ý nhận về từ FastAPI thành danh sách DTO của Java.
     */
    private List<RecommendationDto> parseRecommendations(String body) throws Exception {
        JsonNode root = objectMapper.readTree(body);
        JsonNode recommendationNodes = root.path("recommendations");
        List<RecommendationDto> recommendations = new ArrayList<>();

        if (!recommendationNodes.isArray()) {
            return recommendations;
        }

        for (JsonNode node : recommendationNodes) {
            recommendations.add(new RecommendationDto(
                node.path("track_id").asText(),
                node.path("track_name").asText(),
                node.path("artist").asText(),
                node.path("album").asText(""),
                node.path("genre").asText(),
                node.path("popularity").isMissingNode() ? 0 : node.path("popularity").asInt(),
                node.path("score").isMissingNode() ? 0.0 : node.path("score").asDouble(),
                node.path("reason").asText("Recommended by similar audio features")
            ));
        }

        return recommendations;
    }

    /**
     * Giải mã chuỗi JSON thông tin người dùng demo nhận về từ FastAPI.
     */
    private List<UserProfileDto> parseDemoUsers(String body) throws Exception {
        JsonNode root = objectMapper.readTree(body);
        JsonNode userNodes = root.path("users");
        List<UserProfileDto> users = new ArrayList<>();

        if (!userNodes.isArray()) {
            return users;
        }

        for (JsonNode node : userNodes) {
            List<String> topArtists = new ArrayList<>();
            JsonNode topArtistNodes = node.path("top_artists");
            if (topArtistNodes.isArray()) {
                for (JsonNode artistNode : topArtistNodes) {
                    topArtists.add(artistNode.asText());
                }
            }

            users.add(new UserProfileDto(
                node.path("user_id").asText(),
                topArtists,
                node.path("interactions").isMissingNode() ? 0 : node.path("interactions").asInt()
            ));
        }

        return users;
    }

    /**
     * Cơ chế dự phòng (Fallback Mechanism):
     * Nếu không thể kết nối tới FastAPI (ví dụ server AI bị sập), hệ thống sẽ tự động gọi cơ sở dữ liệu
     * MySQL và lấy các bài hát phổ biến nhất hiển thị cho người dùng, đảm bảo trải nghiệm liền mạch.
     */
    private List<RecommendationDto> fallbackPopularRecommendations(int limit) {
        List<Song> popularSongs = songService.findTopPopular(limit);
        List<RecommendationDto> fallback = new ArrayList<>();

        for (Song song : popularSongs) {
            fallback.add(new RecommendationDto(
                song.getTrackId(),
                song.getTrackName(),
                song.getArtists(),
                "",
                song.getTrackGenre(),
                song.getPopularity(),
                song.getPopularity() == null ? 0.0 : song.getPopularity().doubleValue(),
                "Dự phòng: Gợi ý các bài hát phổ biến do dịch vụ AI tạm thời không phản hồi"
            ));
        }

        return fallback;
    }

    /**
     * Gửi phản hồi (Like/Dislike) của người dùng hiện tại sang FastAPI để cập nhật tức thời gu nhạc.
     * Sử dụng phương thức POST.
     */
    @Override
    public void submitFeedback(String userId, String trackId, String feedbackType) {
        try {
            // Tạo chuỗi Payload JSON thủ công để gửi đi
            String jsonPayload = String.format(
                "{\"user_id\":\"%s\",\"track_id\":\"%s\",\"feedback_type\":\"%s\"}",
                userId.replace("\"", "\\\""),
                trackId.replace("\"", "\\\""),
                feedbackType.replace("\"", "\\\"")
            );

            URI uri = URI.create(aiBaseUrl + "/feedback");
            HttpRequest request = HttpRequest.newBuilder(uri)
                .timeout(Duration.ofSeconds(3))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(jsonPayload, StandardCharsets.UTF_8))
                .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("AI service feedback returned status " + response.statusCode());
            }
        } catch (Exception e) {
            throw new RuntimeException("Không thể gửi phản hồi tới AI Service", e);
        }
    }

    /**
     * Reset toàn bộ gu nhạc (Xóa likes/dislikes) của người dùng trên FastAPI.
     */
    @Override
    public void resetFeedback(String userId) {
        try {
            String encodedUserId = URLEncoder.encode(userId, StandardCharsets.UTF_8);
            URI uri = URI.create(aiBaseUrl + "/feedback/reset/" + encodedUserId);
            HttpRequest request = HttpRequest.newBuilder(uri)
                .timeout(Duration.ofSeconds(3))
                .POST(HttpRequest.BodyPublishers.noBody()) // Gửi POST không chứa body
                .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("AI service reset feedback returned status " + response.statusCode());
            }
        } catch (Exception e) {
            throw new RuntimeException("Không thể reset tùy chọn gu nhạc trên AI Service", e);
        }
    }

    /**
     * Gọi FastAPI để tìm kiếm MV bài hát trên YouTube.
     * 
     * @param query Từ khóa tìm kiếm bài hát ca sĩ
     * @return String videoId của YouTube (ví dụ: dQw4w9WgXcQ)
     */
    @Override
    public String searchYoutube(String query) {
        try {
            String encodedQuery = URLEncoder.encode(query, StandardCharsets.UTF_8);
            URI uri = URI.create(aiBaseUrl + "/youtube/search?q=" + encodedQuery);
            HttpRequest request = HttpRequest.newBuilder(uri)
                .timeout(Duration.ofSeconds(4))
                .GET()
                .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 200 && response.statusCode() < 300) {
                JsonNode root = objectMapper.readTree(response.body());
                return root.path("video_id").asText("");
            }
        } catch (Exception ignored) {
        }
        return "";
    }

    /**
     * Gửi yêu cầu lấy gợi ý trộn gu nhạc Taste Blend giữa 2 người dùng.
     */
    @Override
    public Object recommendBlend(String user1, String user2, int topN) {
        try {
            String encodedUser1 = URLEncoder.encode(user1, StandardCharsets.UTF_8);
            String encodedUser2 = URLEncoder.encode(user2, StandardCharsets.UTF_8);
            URI uri = URI.create(aiBaseUrl + "/recommend/blend?user1=" + encodedUser1 + "&user2=" + encodedUser2 + "&top_n=" + topN);
            HttpRequest request = HttpRequest.newBuilder(uri)
                .timeout(Duration.ofSeconds(4))
                .GET()
                .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 200 && response.statusCode() < 300) {
                return objectMapper.readTree(response.body());
            }
            throw new IllegalStateException("AI service blend returned status " + response.statusCode());
        } catch (Exception e) {
            throw new RuntimeException("Không thể tải danh sách gợi ý Blend", e);
        }
    }

    /**
     * Đồng bộ hóa gu nhạc lịch sử:
     * Dọn sạch các feedback in-memory cũ của tài khoản trên FastAPI, sau đó đẩy lại toàn bộ lịch sử 
     * likes/dislikes hiện tại đang lưu trong MySQL của tài khoản đó.
     */
    @Override
    public void syncUserFeedback(String userId, List<com.example.musicrecommender.entity.UserFeedback> feedbackList) {
        try {
            resetFeedback(userId);
            if (feedbackList != null) {
                for (com.example.musicrecommender.entity.UserFeedback fb : feedbackList) {
                    submitFeedback(userId, fb.getSong().getTrackId(), fb.getFeedbackType());
                }
            }
        } catch (Exception ignored) {
            // Không làm sập luồng chính của app nếu AI service tạm thời không kết nối được
        }
    }
}
