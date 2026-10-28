package com.shumuzengxiao.smartcattle.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;

@Component
public class ApiKeyAccessInterceptor implements HandlerInterceptor {
    private final ApiKeyAccessPolicy policy;

    public ApiKeyAccessInterceptor(ApiKeyAccessPolicy policy) {
        this.policy = policy;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws IOException {
        // CORS preflight has no credentials. Origin validation remains in CorsConfig.
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String role = policy.roleFor(ApiKeyAccessPolicy.bearer(request.getHeader("Authorization")));
        if (role == null) {
            reject(response, HttpServletResponse.SC_UNAUTHORIZED, "API key required");
            return false;
        }
        if (!policy.allowsRest(role, request.getMethod(), request.getRequestURI())) {
            reject(response, HttpServletResponse.SC_FORBIDDEN, "API key role is not authorized for this operation");
            return false;
        }
        request.setAttribute("apiRole", role);
        return true;
    }

    private static void reject(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"message\":\"" + message + "\"}");
    }
}
