package com.example.musicrecommender.service.impl;

import com.example.musicrecommender.entity.Song;
import com.example.musicrecommender.repository.SongRepository;
import com.example.musicrecommender.service.SongService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Service
public class SongServiceImpl implements SongService {

    private final SongRepository songRepository;

    @Autowired
    public SongServiceImpl(SongRepository songRepository) {
        this.songRepository = songRepository;
    }

    @Override
    public List<Song> findAll() {
        return songRepository.findAll();
    }

    @Override
    public Optional<Song> findById(String trackId) {
        return songRepository.findById(trackId);
    }

    @Override
    public List<Song> findTopPopular(int limit) {
        return songRepository.findAll().stream()
            .sorted((left, right) -> Integer.compare(
                right.getPopularity() == null ? 0 : right.getPopularity(),
                left.getPopularity() == null ? 0 : left.getPopularity()
            ))
            .limit(limit)
            .toList();
    }

    @Override
    public List<Song> searchSongs(String query) {
        if (query == null || query.isBlank()) {
            return songRepository.findTop20ByOrderByPopularityDescTrackNameAsc();
        }

        return songRepository.findTop50ByTrackNameContainingIgnoreCaseOrArtistsContainingIgnoreCase(query, query);
    }

    @Override
    public Song save(Song song) {
        return songRepository.save(song);
    }

    @Override
    public void deleteById(String trackId) {
        songRepository.deleteById(trackId);
    }
}
