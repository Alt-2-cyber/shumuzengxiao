package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.ControlCommandRecord;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ControlCommandRecordRepository extends JpaRepository<ControlCommandRecord, Long> {
    List<ControlCommandRecord> findTop20ByOrderByQueuedAtDesc();
}
