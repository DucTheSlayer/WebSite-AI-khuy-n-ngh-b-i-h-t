package com.example.musicrecommender.dto;

import java.util.List;

public record UserProfileDto(
    String userId,
    List<String> topArtists,
    Integer interactions
) {
}
