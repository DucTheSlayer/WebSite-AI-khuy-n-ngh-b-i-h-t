package com.example.musicrecommender.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import java.util.List;

@Data
@AllArgsConstructor
public class AuthResponseDto {
    private String token;
    private String username;
    private String email;
    private String fullName;
    private List<String> likedSongIds;
    private List<String> dislikedSongIds;
}
