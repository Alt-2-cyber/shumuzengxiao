package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.Device;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface DeviceRepository extends JpaRepository<Device, Long> {
    List<Device> findByBarnId(String barnId);
}
