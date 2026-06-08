package com.example.musicrecommender.repository;

import com.example.musicrecommender.entity.Song;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface SongRepository extends JpaRepository<Song, String> {
    List<Song> findTop20ByOrderByPopularityDescTrackNameAsc();
    List<Song> findTop50ByTrackNameContainingIgnoreCaseOrArtistsContainingIgnoreCase(String trackName, String artists);
}
