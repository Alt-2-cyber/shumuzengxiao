package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shumuzengxiao.smartcattle.domain.MobileConsultation;
import com.shumuzengxiao.smartcattle.dto.MobileSupport.*;
import com.shumuzengxiao.smartcattle.repository.MobileConsultationRepository;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.server.ResponseStatusException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class MobileSupportTest {
    private final String token = "a".repeat(48);

    @Test
    void knowledgeAnswersUseRelevantEvidenceAndDoNotClaimADiagnosis() {
        CattleKnowledgeService knowledge = new CattleKnowledgeService();
        assertThat(knowledge.answer("牛只流涎，有口蹄水疱").answer()).contains("不能单独确诊", "当地兽医");
        assertThat(knowledge.answer("B-1 红外温度偏高").answer()).contains("表面温度", "核心体温");
        assertThat(knowledge.answer("腿部跛行怎么观察").category()).isEqualTo("health");
        assertThat(knowledge.answer("你好").category()).isEqualTo("other");
        assertThat(knowledge.answer("wifi 离线").mode()).isEqualTo("knowledge");
    }

    @Test
    void gatewaySendsHistoryAndReturnsRealModelOutputOrLabeledFallback() throws Exception {
        AtomicReference<String> body = new AtomicReference<>();
        AtomicReference<String> response = new AtomicReference<>("{\"choices\":[{\"message\":{\"content\":\"请记录连续步态与采食情况。\"}}]}");
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/chat/completions", exchange -> {
            body.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] data = response.get().getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, data.length);
            exchange.getResponseBody().write(data);
            exchange.close();
        });
        server.start();
        try {
            MobileAssistantService assistant = new MobileAssistantService(new CattleKnowledgeService(), new ObjectMapper());
            ReflectionTestUtils.setField(assistant, "endpoint", "http://127.0.0.1:" + server.getAddress().getPort() + "/chat/completions");
            ReflectionTestUtils.setField(assistant, "apiKey", "test-only");
            ReflectionTestUtils.setField(assistant, "model", "deepseek-chat");
            Answer result = assistant.answer(new Question("有跛行怎么办", List.of(new Message("user", "耳标 C-01"))));
            assertThat(result.mode()).isEqualTo("llm");
            assertThat(result.answer()).contains("连续步态");
            assertThat(body.get()).contains("deepseek-chat", "C-01");
            response.set("{\"choices\":[]}");
            Answer fallback = assistant.answer(new Question("有跛行怎么办", List.of()));
            assertThat(fallback.mode()).isEqualTo("knowledge");
            assertThat(fallback.notice()).contains("切换知识库");
        } finally { server.stop(0); }
    }

    @Test
    void retriesAreIdempotentAndAnotherClientCannotCancelOrReuseAnOwnedRecord() {
        MobileConsultationRepository repository = mock(MobileConsultationRepository.class);
        MobileConsultationService service = new MobileConsultationService(repository);
        ConsultationRequest request = new ConsultationRequest("wx_consultation_001", "health", "soon",
                "牛只连续两天出现跛行", "连续两天活动减少，右腿不愿负重，未测核心体温。", "C-01", "");
        MobileConsultation[] saved = new MobileConsultation[1];
        when(repository.findById(request.requestId())).thenAnswer(call -> Optional.ofNullable(saved[0]));
        when(repository.saveAndFlush(any())).thenAnswer(call -> { saved[0] = call.getArgument(0); return saved[0]; });
        assertThat(service.submit(token, request).status()).isEqualTo("pending");
        assertThat(service.submit(token, request).id()).isEqualTo(request.requestId());
        verify(repository, times(1)).saveAndFlush(any());
        assertThatThrownBy(() -> service.submit("b".repeat(48), request)).isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(() -> service.cancel("b".repeat(48), request.requestId())).isInstanceOf(ResponseStatusException.class);
        assertThat(service.cancel(token, request.requestId()).status()).isEqualTo("cancelled");
        assertThatThrownBy(() -> service.list("short")).isInstanceOf(ResponseStatusException.class);
    }
}
