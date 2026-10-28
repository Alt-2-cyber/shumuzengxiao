package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.HealthScreeningObservation;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.Instant;
import java.util.List;

public interface HealthScreeningObservationRepository extends JpaRepository<HealthScreeningObservation, Long> {
    List<HealthScreeningObservation> findByReceivedAtAfterOrderByReceivedAtAsc(Instant cutoff);

    long deleteByReceivedAtBefore(Instant cutoff);
}
