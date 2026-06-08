package com.example.musicrecommender.controller;

import com.example.musicrecommender.dto.RecommendationDto;
import com.example.musicrecommender.dto.UserProfileDto;
import com.example.musicrecommender.entity.Song;
import com.example.musicrecommender.service.AiRecommendationService;
import com.example.musicrecommender.service.SongService;
import com.example.musicrecommender.dto.FeedbackRequestDto;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
public class SongController {

    private final SongService songService;
    private final AiRecommendationService aiRecommendationService;

    @Autowired
    public SongController(SongService songService, AiRecommendationService aiRecommendationService) {
        this.songService = songService;
        this.aiRecommendationService = aiRecommendationService;
    }

    @GetMapping("/api/songs")
    public List<Song> allSongs(@RequestParam(required = false) String q) {
        if (q != null) {
            return songService.searchSongs(q);
        }
        return songService.findAll();
    }

    @GetMapping({"/api/song/{id}", "/api/songs/{id}"})
    public Song getSong(@PathVariable String id) {
        return songService.findById(id).orElse(null);
    }

    @GetMapping("/api/recommend/{trackId}")
    public List<RecommendationDto> recommendByTrack(
        @PathVariable String trackId,
        @RequestParam(defaultValue = "10") int topN
    ) {
        return aiRecommendationService.recommendByTrack(trackId, topN);
    }

    @GetMapping("/api/recommend/user/{userId}")
    public List<RecommendationDto> recommendByUser(
        @PathVariable String userId,
        @RequestParam(defaultValue = "10") int topN
    ) {
        return aiRecommendationService.recommendByUser(userId, topN);
    }

    @GetMapping("/api/users/demo")
    public List<UserProfileDto> demoUsers(@RequestParam(defaultValue = "12") int limit) {
        return aiRecommendationService.getDemoUsers(limit);
    }

    @GetMapping("/api/popular")
    public List<Song> popularSongs(@RequestParam(defaultValue = "10") int limit) {
        return songService.findTopPopular(limit);
    }

    @GetMapping("/")
    public String home() {
        return "API dang chay. Dung /api/songs, /api/songs/{id}, /api/recommend/{trackId}";
    }

    @PostMapping("/api/feedback")
    public ResponseEntity<?> submitFeedback(@RequestBody FeedbackRequestDto request) {
        try {
            aiRecommendationService.submitFeedback(
                request.getUserId(),
                request.getTrackId(),
                request.getFeedbackType()
            );
            return ResponseEntity.ok().body(java.util.Map.of("status", "success"));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(java.util.Map.of("error", e.getMessage()));
        }
    }

    @PostMapping("/api/feedback/reset/{userId}")
    public ResponseEntity<?> resetFeedback(@PathVariable String userId) {
        try {
            aiRecommendationService.resetFeedback(userId);
            return ResponseEntity.ok().body(java.util.Map.of("status", "success"));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(java.util.Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/api/youtube/search")
    public ResponseEntity<?> searchYoutube(@RequestParam String q) {
        try {
            String videoId = aiRecommendationService.searchYoutube(q);
            return ResponseEntity.ok().body(java.util.Map.of("video_id", videoId));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(java.util.Map.of("error", e.getMessage()));
        }
    }

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
