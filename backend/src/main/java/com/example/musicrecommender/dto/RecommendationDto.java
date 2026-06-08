package com.example.musicrecommender.dto;

public record RecommendationDto(
    String trackId,
    String trackName,
    String artist,
    String album,
    String genre,
    Integer popularity,
    Double score,
    String reason
) {
}
