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

@Service
public class AiRecommendationServiceImpl implements AiRecommendationService {

    private final SongService songService;
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;
    private final String aiBaseUrl;
    private final int topPopularFallback;

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
        this.httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(timeoutSeconds))
            .build();
    }

    @Override
    public List<RecommendationDto> recommendByTrack(String trackId, int topN) {
        try {
            String encodedTrackId = URLEncoder.encode(trackId, StandardCharsets.UTF_8);
            return fetchRecommendations("/recommend/" + encodedTrackId + "?top_n=" + topN);
        } catch (Exception ignored) {
            // Fallback handled below.
        }

        return fallbackPopularRecommendations(Math.min(topN, topPopularFallback));
    }

    @Override
    public List<RecommendationDto> recommendByUser(String userId, int topN) {
        try {
            String encodedUserId = URLEncoder.encode(userId, StandardCharsets.UTF_8);
            return fetchRecommendations("/recommend/user/" + encodedUserId + "?top_n=" + topN);
        } catch (Exception ignored) {
            // Fallback handled below.
        }

        return fallbackPopularRecommendations(Math.min(topN, topPopularFallback));
    }

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
            // Empty list handled below.
        }

        return List.of();
    }

    private List<RecommendationDto> fetchRecommendations(String pathAndQuery) throws Exception {
        URI uri = URI.create(aiBaseUrl + pathAndQuery);
        HttpRequest request = HttpRequest.newBuilder(uri)
            .timeout(Duration.ofSeconds(3))
            .GET()
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() >= 200 && response.statusCode() < 300) {
            return parseRecommendations(response.body());
        }

        throw new IllegalStateException("AI service returned status " + response.statusCode());
    }

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
                "Fallback recommendation because AI service is unavailable; showing popular songs"
            ));
        }

        return fallback;
    }

    @Override
    public void submitFeedback(String userId, String trackId, String feedbackType) {
        try {
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
            throw new RuntimeException("Failed to submit feedback to AI service", e);
        }
    }

    @Override
    public void resetFeedback(String userId) {
        try {
            String encodedUserId = URLEncoder.encode(userId, StandardCharsets.UTF_8);
            URI uri = URI.create(aiBaseUrl + "/feedback/reset/" + encodedUserId);
            HttpRequest request = HttpRequest.newBuilder(uri)
                .timeout(Duration.ofSeconds(3))
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("AI service reset feedback returned status " + response.statusCode());
            }
        } catch (Exception e) {
            throw new RuntimeException("Failed to reset feedback in AI service", e);
        }
    }

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
            throw new RuntimeException("Failed to fetch blend recommendations", e);
        }
    }
}
