package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.ClinicalCheck;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ClinicalCheckRepository extends JpaRepository<ClinicalCheck, Long> {
    List<ClinicalCheck> findTop100ByCattleIdOrderByRecordedAtDesc(String cattleId);
    List<ClinicalCheck> findTop500ByOrderByRecordedAtDesc();
}
