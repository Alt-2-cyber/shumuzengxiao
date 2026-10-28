package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.AudioEventReview;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface AudioEventReviewRepository extends JpaRepository<AudioEventReview, Long> {
    Optional<AudioEventReview> findByAudioEventId(Long audioEventId);
    List<AudioEventReview> findByAudioEventIdIn(Collection<Long> audioEventIds);
}
