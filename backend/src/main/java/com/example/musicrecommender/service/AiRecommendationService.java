package com.example.musicrecommender.service;

import com.example.musicrecommender.dto.RecommendationDto;
import com.example.musicrecommender.dto.UserProfileDto;

import java.util.List;

public interface AiRecommendationService {
    List<RecommendationDto> recommendByTrack(String trackId, int topN);
    List<RecommendationDto> recommendByUser(String userId, int topN);
    List<UserProfileDto> getDemoUsers(int limit);
    void submitFeedback(String userId, String trackId, String feedbackType);
    void resetFeedback(String userId);
    String searchYoutube(String query);
    Object recommendBlend(String user1, String user2, int topN);
}
