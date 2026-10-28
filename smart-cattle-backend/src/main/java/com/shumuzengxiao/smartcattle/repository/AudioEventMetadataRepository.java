package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.AudioEventMetadata;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface AudioEventMetadataRepository extends JpaRepository<AudioEventMetadata, Long> {
    List<AudioEventMetadata> findByAudioEventIdIn(Collection<Long> audioEventIds);
    Optional<AudioEventMetadata> findByAudioEventId(Long audioEventId);
    Optional<AudioEventMetadata> findBySourceKey(String sourceKey);
}
