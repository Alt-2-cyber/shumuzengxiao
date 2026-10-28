package com.shumuzengxiao.smartcattle.config;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ApiKeyAccessPolicyTest {
    @Test
    void assignsRolesAndRestrictsMutatingEndpoints() {
        ApiKeyAccessPolicy policy = policy();

        assertThat(policy.roleFor("ingest-secret")).isEqualTo("ingest");
        assertThat(policy.roleFor("clinical-secret")).isEqualTo("clinical");
        assertThat(policy.roleFor("wrong-secret")).isNull();
        assertThat(policy.allowsRest("ingest", "POST", "/api/events/vision")).isTrue();
        assertThat(policy.allowsRest("ingest", "POST", "/api/clinical-checks")).isFalse();
        assertThat(policy.allowsRest("clinical", "POST", "/api/clinical-checks")).isTrue();
        assertThat(policy.allowsRest("clinical", "PUT", "/api/events/audio/1/review")).isTrue();
        assertThat(policy.allowsRest("clinical", "GET", "/api/events/audio/1/training-lineage")).isTrue();
        assertThat(policy.allowsRest("clinical", "GET", "/api/motion-captures/session_001/training-lineage")).isTrue();
        assertThat(policy.allowsRest("clinical", "PUT", "/api/motion-captures/session_001/clinical-review")).isTrue();
        assertThat(policy.allowsRest("clinical", "GET", "/api/audio-clips/sample.wav")).isTrue();
        assertThat(policy.allowsRest("clinical", "GET", "/api/events/vision")).isTrue();
        assertThat(policy.allowsRest("viewer", "GET", "/api/clinical-checks")).isFalse();
        assertThat(policy.allowsRest("viewer", "GET", "/api/events/audio")).isFalse();
        assertThat(policy.allowsRest("viewer", "GET", "/api/events/audio/1/training-lineage")).isFalse();
        assertThat(policy.allowsRest("viewer", "GET", "/api/motion-captures/session_001/training-lineage")).isFalse();
        assertThat(policy.allowsRest("viewer", "PUT", "/api/motion-captures/session_001/clinical-review")).isFalse();
        assertThat(policy.allowsRest("viewer", "GET", "/api/events/vision")).isFalse();
        assertThat(policy.allowsRest("viewer", "GET", "/api/model-releases")).isFalse();
        assertThat(policy.allowsRest("viewer", "GET", "/api/dashboard")).isTrue();
        assertThat(policy.allowsRest("viewer", "POST", "/api/mobile-support/assistant")).isTrue();
        assertThat(policy.allowsRest("viewer", "POST", "/api/mobile-support/consultations")).isTrue();
        assertThat(policy.allowsRest("ingest", "GET", "/api/mobile-support/consultations")).isFalse();
        assertThat(policy.allowsRest("viewer", "DELETE", "/api/mobile-support/consultations/a")).isFalse();
        assertThat(policy.allowsRest("viewer", "POST", "/api/devices/command")).isFalse();
        assertThat(policy.allowsRest("admin", "POST", "/api/events/health-risks")).isFalse();
        assertThat(policy.allowsRest("admin", "POST", "/api/events/audio")).isFalse();
        assertThat(policy.allowsWebSocket("viewer")).isTrue();
        assertThat(policy.allowsWebSocket("ingest")).isFalse();
    }

    @Test
    void allowsCorsPreflightWithoutASecretButRejectsUnauthenticatedApiCalls() throws Exception {
        ApiKeyAccessInterceptor interceptor = new ApiKeyAccessInterceptor(policy());
        MockHttpServletResponse response = new MockHttpServletResponse();

        assertThat(interceptor.preHandle(
                new MockHttpServletRequest("OPTIONS", "/api/events/vision"), response, new Object())).isTrue();

        MockHttpServletResponse rejected = new MockHttpServletResponse();
        assertThat(interceptor.preHandle(
                new MockHttpServletRequest("GET", "/api/dashboard"), rejected, new Object())).isFalse();
        assertThat(rejected.getStatus()).isEqualTo(401);
    }

    @Test
    void rejectsDuplicateRoleSecretsAtStartup() {
        ApiKeyAccessPolicy policy = policy();
        ReflectionTestUtils.setField(policy, "viewerKey", "admin-secret");

        assertThatThrownBy(policy::validateConfiguration)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("unique across roles");
    }

    @Test
    void productionRoleModeRequiresEveryScopedSecret() {
        ApiKeyAccessPolicy policy = policy();
        ReflectionTestUtils.setField(policy, "requireRoleKeys", true);
        ReflectionTestUtils.setField(policy, "ingestKey", "");

        assertThatThrownBy(policy::validateConfiguration)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("requires every role key: ingest");
    }

    @Test
    void productionRoleModeCannotBeOverriddenToDisableAuthentication() {
        ApiKeyAccessPolicy policy = policy();
        ReflectionTestUtils.setField(policy, "requireRoleKeys", true);
        ReflectionTestUtils.setField(policy, "enabled", false);

        assertThatThrownBy(policy::validateConfiguration)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("cannot disable API-key authentication");
    }

    private static ApiKeyAccessPolicy policy() {
        ApiKeyAccessPolicy policy = new ApiKeyAccessPolicy();
        ReflectionTestUtils.setField(policy, "enabled", true);
        ReflectionTestUtils.setField(policy, "adminKey", "admin-secret");
        ReflectionTestUtils.setField(policy, "clinicalKey", "clinical-secret");
        ReflectionTestUtils.setField(policy, "operatorKey", "operator-secret");
        ReflectionTestUtils.setField(policy, "viewerKey", "viewer-secret");
        ReflectionTestUtils.setField(policy, "ingestKey", "ingest-secret");
        return policy;
    }
}
