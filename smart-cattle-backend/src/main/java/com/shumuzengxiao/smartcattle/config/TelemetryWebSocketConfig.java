package com.shumuzengxiao.smartcattle.config;

import com.shumuzengxiao.smartcattle.websocket.TelemetryWebSocketHandler;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket
public class TelemetryWebSocketConfig implements WebSocketConfigurer {
    private final TelemetryWebSocketHandler handler;
    private final ApiKeyWebSocketHandshakeInterceptor apiKeyHandshake;

    @Value("${security.cors.allowed-origins:http://localhost:5173,http://127.0.0.1:5173}")
    private String allowedOrigins;

    public TelemetryWebSocketConfig(
            TelemetryWebSocketHandler handler,
            ApiKeyWebSocketHandshakeInterceptor apiKeyHandshake
    ) {
        this.handler = handler;
        this.apiKeyHandshake = apiKeyHandshake;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(handler, "/ws/telemetry")
                .addInterceptors(apiKeyHandshake)
                .setAllowedOriginPatterns(allowedOrigins.split(","));
    }
}
