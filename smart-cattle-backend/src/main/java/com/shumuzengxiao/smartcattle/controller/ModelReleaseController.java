package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.domain.ModelRelease;
import com.shumuzengxiao.smartcattle.dto.ModelReleaseRequest;
import com.shumuzengxiao.smartcattle.dto.ModelReleaseRevocationRequest;
import com.shumuzengxiao.smartcattle.service.ModelReleaseService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/model-releases")
public class ModelReleaseController {
    private final ModelReleaseService releases;

    public ModelReleaseController(ModelReleaseService releases) {
        this.releases = releases;
    }

    @GetMapping
    public List<ModelRelease> recent() {
        return releases.recent();
    }

    @PostMapping
    public ModelRelease approve(@Valid @RequestBody ModelReleaseRequest request) {
        return releases.approve(request);
    }

    @PostMapping("/{releaseId}/revoke")
    public ModelRelease revoke(
            @PathVariable Long releaseId,
            @Valid @RequestBody ModelReleaseRevocationRequest request
    ) {
        return releases.revoke(releaseId, request);
    }
}
