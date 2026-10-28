package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.MotionCaptureSession;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.time.Instant;

public interface MotionCaptureSessionRepository extends JpaRepository<MotionCaptureSession, Long> {
    Optional<MotionCaptureSession> findBySessionId(String sessionId);
    List<MotionCaptureSession> findTop100ByOrderByRequestedAtDesc();
    List<MotionCaptureSession> findTop100ByCattleIdOrderByRequestedAtDesc(String cattleId);
    List<MotionCaptureSession> findByStatusInAndRequestedAtBefore(List<String> statuses, Instant cutoff);
}
