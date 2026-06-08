package com.example.musicrecommender.service;

import com.example.musicrecommender.entity.Song;

import java.util.List;
import java.util.Optional;

public interface SongService {
    List<Song> findAll();
    Optional<Song> findById(String trackId);
    List<Song> findTopPopular(int limit);
    List<Song> searchSongs(String query);
    Song save(Song song);
    void deleteById(String trackId);
}
