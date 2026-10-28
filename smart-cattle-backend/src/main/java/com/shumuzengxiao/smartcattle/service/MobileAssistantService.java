package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.shumuzengxiao.smartcattle.dto.MobileSupport.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class MobileAssistantService {
    private final CattleKnowledgeService knowledge;
    private final ObjectMapper mapper;
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
    @Value("${app.assistant.endpoint:}") private String endpoint = "";
    @Value("${app.assistant.api-key:}") private String apiKey = "";
    @Value("${app.assistant.model:}") private String model = "";

    public MobileAssistantService(CattleKnowledgeService knowledge, ObjectMapper mapper) {
        this.knowledge = knowledge;
        this.mapper = mapper;
    }

    public boolean modelConfigured() {
        return !endpoint.isBlank() && !apiKey.isBlank() && !model.isBlank();
    }

    public Answer answer(Question request) {
        Answer evidence = knowledge.answer(request.question());
        if (!modelConfigured()) { return evidence; }
        try {
            List<Map<String, String>> messages = new ArrayList<>();
            messages.add(Map.of("role", "system", "content", "你是数牧增效的养殖巡检助手。使用简洁中文，以纯文本和编号列表回答，不使用 Markdown 标记。"
                    + "仅提供养殖管理、数据解释和就医分流建议，不确诊疾病，不编造兽医、实时数据或检测结果，不给用药剂量。"
                    + "疑似传染病、严重呼吸困难等应建议及时联系当地兽医。B-1 是体表测温，声音和加速度是观察线索。"
                    + "以下为可参考的项目知识，不要声称已访问实时设备：\n" + evidence.answer()));
            if (request.history() != null) {
                for (Message message : request.history()) {
                    messages.add(Map.of("role", message.role(), "content", message.content()));
                }
            }
            messages.add(Map.of("role", "user", "content", request.question()));
            String body = mapper.writeValueAsString(Map.of("model", model, "messages", messages,
                    "temperature", 0.2, "max_tokens", 900, "stream", false));
            HttpRequest httpRequest = HttpRequest.newBuilder(URI.create(endpoint))
                    .timeout(Duration.ofSeconds(18)).header("Content-Type", "application/json")
                    .header("Authorization", "Bearer " + apiKey).POST(HttpRequest.BodyPublishers.ofString(body)).build();
            HttpResponse<String> response = client.send(httpRequest, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200 || response.body().length() > 200_000) {
                throw new IllegalStateException("Invalid assistant response");
            }
            JsonNode content = mapper.readTree(response.body()).path("choices").path(0).path("message").path("content");
            if (!content.isTextual() || content.asText().isBlank()) {
                throw new IllegalStateException("Empty assistant response");
            }
            String answer = content.asText();
            return new Answer(answer.substring(0, Math.min(answer.length(), 8000)), "llm", model,
                    "", evidence.category(), evidence.references());
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        } catch (Exception unavailable) {
            // Provider diagnostics can contain credentials or user text; keep them out of client errors.
        }
        return new Answer(evidence.answer(), "knowledge", evidence.model(),
                "大模型暂不可用，已切换知识库", evidence.category(), evidence.references());
    }
}
