package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.AlertRecord;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface AlertRecordRepository extends JpaRepository<AlertRecord, Long> {
    List<AlertRecord> findTop30ByOrderByCreatedAtDesc();
    List<AlertRecord> findTop30ByBarnIdOrderByCreatedAtDesc(String barnId);
}
