package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.VisionEventReview;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface VisionEventReviewRepository extends JpaRepository<VisionEventReview, Long> {
    Optional<VisionEventReview> findByVisionEventId(Long visionEventId);
    List<VisionEventReview> findByVisionEventIdIn(Collection<Long> visionEventIds);
}
