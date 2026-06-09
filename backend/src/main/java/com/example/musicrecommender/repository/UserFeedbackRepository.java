package com.example.musicrecommender.repository;

import com.example.musicrecommender.entity.Song;
import com.example.musicrecommender.entity.User;
import com.example.musicrecommender.entity.UserFeedback;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface UserFeedbackRepository extends JpaRepository<UserFeedback, Long> {
    Optional<UserFeedback> findByUserAndSong(User user, Song song);
    List<UserFeedback> findByUser(User user);
    List<UserFeedback> findByUserAndFeedbackType(User user, String feedbackType);
    void deleteByUser(User user);
}
