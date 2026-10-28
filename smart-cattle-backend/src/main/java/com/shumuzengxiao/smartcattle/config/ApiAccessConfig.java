package com.shumuzengxiao.smartcattle.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class ApiAccessConfig implements WebMvcConfigurer {
    private final ApiKeyAccessInterceptor apiKeyAccess;

    public ApiAccessConfig(ApiKeyAccessInterceptor apiKeyAccess) {
        this.apiKeyAccess = apiKeyAccess;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(apiKeyAccess).addPathPatterns("/api/**");
    }
}
