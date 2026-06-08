package com.example.musicrecommender.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Column;
import lombok.Data;

@Data
@Entity
public class Song {
    @Id
    private String trackId;
    @Column(length = 1024)
    private String trackName;
    @Column(length = 2048)
    private String artists;
    @Column(length = 128)
    private String trackGenre;
    private Integer popularity;
}
