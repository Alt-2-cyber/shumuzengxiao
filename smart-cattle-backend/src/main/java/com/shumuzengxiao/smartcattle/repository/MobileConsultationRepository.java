package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.MobileConsultation;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface MobileConsultationRepository extends JpaRepository<MobileConsultation, String> {
    List<MobileConsultation> findTop50ByOwnerHashOrderByCreatedAtDesc(String ownerHash);
}
