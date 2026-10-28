package com.shumuzengxiao.smartcattle.service;

import com.shumuzengxiao.smartcattle.domain.MobileConsultation;
import com.shumuzengxiao.smartcattle.dto.MobileSupport.ConsultationRequest;
import com.shumuzengxiao.smartcattle.dto.MobileSupport.ConsultationView;
import com.shumuzengxiao.smartcattle.repository.MobileConsultationRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;

@Service
public class MobileConsultationService {
    private final MobileConsultationRepository repository;

    public MobileConsultationService(MobileConsultationRepository repository) { this.repository = repository; }

    public synchronized ConsultationView submit(String token, ConsultationRequest request) {
        String owner = ownerHash(token);
        if (request.subject().trim().length() < 5 || request.description().trim().length() < 10) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "标题或详情字数不足");
        }
        MobileConsultation existing = repository.findById(request.requestId()).orElse(null);
        if (existing != null) {
            if (!existing.ownedBy(owner) || !existing.sameRequest(request)) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "咨询编号已使用，请重新创建咨询");
            }
            return existing.view();
        }
        return repository.saveAndFlush(new MobileConsultation(owner, request)).view();
    }

    public List<ConsultationView> list(String token) {
        return repository.findTop50ByOwnerHashOrderByCreatedAtDesc(ownerHash(token)).stream()
                .map(MobileConsultation::view).toList();
    }

    public synchronized ConsultationView cancel(String token, String id) {
        String owner = ownerHash(token);
        MobileConsultation item = repository.findById(id).filter(value -> value.ownedBy(owner))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "咨询记录不存在"));
        item.cancel();
        return repository.saveAndFlush(item).view();
    }

    private String ownerHash(String token) {
        if (token == null || !token.matches("[a-zA-Z0-9_-]{32,128}")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "缺少有效的客户端身份");
        }
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(token.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }
}
