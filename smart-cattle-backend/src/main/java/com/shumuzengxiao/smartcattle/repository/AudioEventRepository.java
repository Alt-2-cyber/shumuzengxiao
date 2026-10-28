package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.AudioEvent;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface AudioEventRepository extends JpaRepository<AudioEvent, Long> {
    List<AudioEvent> findTop20ByOrderByRecordedAtDesc();
    List<AudioEvent> findTop100ByOrderByRecordedAtDesc();
    List<AudioEvent> findTop100ByBarnIdOrderByRecordedAtDesc(String barnId);
    Optional<AudioEvent> findByAudioClipPath(String audioClipPath);
}
