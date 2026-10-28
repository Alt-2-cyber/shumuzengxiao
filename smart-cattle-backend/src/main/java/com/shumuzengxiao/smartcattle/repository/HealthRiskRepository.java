package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.HealthRisk;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface HealthRiskRepository extends JpaRepository<HealthRisk, Long> {
    List<HealthRisk> findTop20ByOrderByRecordedAtDesc();
    List<HealthRisk> findTop20ByBarnIdOrderByRecordedAtDesc(String barnId);
    List<HealthRisk> findByTargetIdAndStatusOrderByRecordedAtDesc(String targetId, String status);
    List<HealthRisk> findByBarnIdAndTargetIdAndStatusOrderByRecordedAtDesc(String barnId, String targetId, String status);
    Optional<HealthRisk> findFirstByTargetIdAndRiskTypeAndStatusOrderByRecordedAtDesc(
            String targetId, String riskType, String status);
    Optional<HealthRisk> findFirstByBarnIdAndTargetIdAndRiskTypeAndStatusOrderByRecordedAtDesc(
            String barnId, String targetId, String riskType, String status);
}
