package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.FmdTriageCase;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface FmdTriageCaseRepository extends JpaRepository<FmdTriageCase, Long> {
    Optional<FmdTriageCase> findByHealthRiskId(Long healthRiskId);
    List<FmdTriageCase> findTop100ByOrderByOpenedAtDesc();
    List<FmdTriageCase> findTop100ByCattleIdOrderByOpenedAtDesc(String cattleId);
}
