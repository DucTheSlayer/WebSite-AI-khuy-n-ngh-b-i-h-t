package com.example.musicrecommender.dto;

public class FeedbackRequestDto {
    private String userId;
    private String trackId;
    private String feedbackType;

    public FeedbackRequestDto() {}

    public FeedbackRequestDto(String userId, String trackId, String feedbackType) {
        this.userId = userId;
        this.trackId = trackId;
        this.feedbackType = feedbackType;
    }

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public String getTrackId() {
        return trackId;
    }

    public void setTrackId(String trackId) {
        this.trackId = trackId;
    }

    public String getFeedbackType() {
        return feedbackType;
    }

    public void setFeedbackType(String feedbackType) {
        this.feedbackType = feedbackType;
    }
}
