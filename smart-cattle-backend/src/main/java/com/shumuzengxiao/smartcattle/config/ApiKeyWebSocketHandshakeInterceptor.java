package com.shumuzengxiao.smartcattle.config;

import org.springframework.http.HttpStatus;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.util.MultiValueMap;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.server.HandshakeInterceptor;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.Map;

/** Browsers cannot attach arbitrary Authorization headers to a native WebSocket
 * handshake. The query key is a compatibility fallback for a TLS/proxy-protected
 * intranet; deploy a proxy identity layer for internet-facing installations. */
@Component
public class ApiKeyWebSocketHandshakeInterceptor implements HandshakeInterceptor {
    private final ApiKeyAccessPolicy policy;

    public ApiKeyWebSocketHandshakeInterceptor(ApiKeyAccessPolicy policy) {
        this.policy = policy;
    }

    @Override
    public boolean beforeHandshake(
            ServerHttpRequest request,
            ServerHttpResponse response,
            WebSocketHandler wsHandler,
            Map<String, Object> attributes
    ) {
        MultiValueMap<String, String> query = UriComponentsBuilder.fromUri(request.getURI()).build().getQueryParams();
        String role = policy.roleFor(query.getFirst("apiKey"));
        if (role == null) {
            response.setStatusCode(HttpStatus.UNAUTHORIZED);
            return false;
        }
        if (!policy.allowsWebSocket(role)) {
            response.setStatusCode(HttpStatus.FORBIDDEN);
            return false;
        }
        attributes.put("apiRole", role);
        return true;
    }

    @Override
    public void afterHandshake(
            ServerHttpRequest request,
            ServerHttpResponse response,
            WebSocketHandler wsHandler,
            Exception exception
    ) {
        // No resources are allocated by the policy.
    }
}
