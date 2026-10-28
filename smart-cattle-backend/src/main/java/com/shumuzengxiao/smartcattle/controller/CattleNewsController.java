package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.domain.CattleArticle;
import com.shumuzengxiao.smartcattle.service.CattleNewsService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/mobile-support/news")
public class CattleNewsController {
    private final CattleNewsService news;
    public CattleNewsController(CattleNewsService news) { this.news = news; }
    @GetMapping("/feed") public CattleNewsService.Feed feed() { return news.feed(); }
    @GetMapping("/articles/{id}") public CattleArticle article(@PathVariable String id) { return news.article(id); }
}
