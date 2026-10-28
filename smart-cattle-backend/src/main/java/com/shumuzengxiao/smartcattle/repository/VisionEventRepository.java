package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.VisionEvent;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface VisionEventRepository extends JpaRepository<VisionEvent, Long> {
    List<VisionEvent> findTop20ByOrderByRecordedAtDesc();
    List<VisionEvent> findTop20ByBarnIdOrderByRecordedAtDesc(String barnId);
    List<VisionEvent> findTop500ByOrderByRecordedAtDesc();
    Optional<VisionEvent> findBySourceKey(String sourceKey);
    Optional<VisionEvent> findBySnapshotPath(String snapshotPath);
}
