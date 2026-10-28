package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.dto.MobileSupport.*;
import com.shumuzengxiao.smartcattle.service.MobileAssistantService;
import com.shumuzengxiao.smartcattle.service.MobileConsultationService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/mobile-support")
public class MobileSupportController {
    private final MobileAssistantService assistant;
    private final MobileConsultationService consultations;

    public MobileSupportController(MobileAssistantService assistant, MobileConsultationService consultations) {
        this.assistant = assistant;
        this.consultations = consultations;
    }

    @GetMapping("/catalog")
    public Catalog catalog() {
        return new Catalog(assistant.modelConfigured() ? "llm" : "knowledge", List.of(
                new Category("health", "牛病与健康", "跛行、咳嗽、体温与体表异常"),
                new Category("nutrition", "饲养与营养", "采食、反刍、饮水与日粮管理"),
                new Category("equipment", "设备与环境", "传感器、网络、通风与数据排查"),
                new Category("other", "其他问题", "综合巡检与管理问题")));
    }

    public record Session(String token) {}

    @GetMapping("/session")
    public Session session() {
        byte[] bytes = new byte[32];
        new java.security.SecureRandom().nextBytes(bytes);
        return new Session(java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(bytes));
    }

    @PostMapping("/assistant")
    public Answer answer(@Valid @RequestBody Question request) { return assistant.answer(request); }

    @PostMapping("/consultations")
    public ConsultationView submit(@RequestHeader("X-Mobile-Token") String token,
                                   @Valid @RequestBody ConsultationRequest request) {
        return consultations.submit(token, request);
    }

    @GetMapping("/consultations")
    public List<ConsultationView> list(@RequestHeader("X-Mobile-Token") String token) {
        return consultations.list(token);
    }

    @PostMapping("/consultations/{id}/cancel")
    public ConsultationView cancel(@RequestHeader("X-Mobile-Token") String token, @PathVariable String id) {
        return consultations.cancel(token, id);
    }
}
