package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.AuditRecord;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface AuditRecordRepository extends JpaRepository<AuditRecord, Long> {
    Optional<AuditRecord> findTop1ByOrderByIdDesc();
    List<AuditRecord> findTop100ByOrderByIdDesc();
    List<AuditRecord> findTop100ByTargetTypeAndTargetIdOrderByIdDesc(String targetType, String targetId);
}
