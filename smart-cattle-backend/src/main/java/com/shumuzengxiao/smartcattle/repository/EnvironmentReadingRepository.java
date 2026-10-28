package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.EnvironmentReading;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface EnvironmentReadingRepository extends JpaRepository<EnvironmentReading, Long> {
    List<EnvironmentReading> findTop48ByBarnIdOrderByRecordedAtDesc(String barnId);
    EnvironmentReading findTopByBarnIdOrderByRecordedAtDesc(String barnId);
}
