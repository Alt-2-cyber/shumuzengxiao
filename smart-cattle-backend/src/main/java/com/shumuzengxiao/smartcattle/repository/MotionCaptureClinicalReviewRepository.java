package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.MotionCaptureClinicalReview;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface MotionCaptureClinicalReviewRepository extends JpaRepository<MotionCaptureClinicalReview, Long> {
    Optional<MotionCaptureClinicalReview> findBySessionId(String sessionId);
}
