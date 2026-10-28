package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.ModelRelease;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ModelReleaseRepository extends JpaRepository<ModelRelease, Long> {
    Optional<ModelRelease> findByModelFamilyAndModelVersion(String modelFamily, String modelVersion);
    List<ModelRelease> findTop100ByOrderByApprovedAtDesc();
}
