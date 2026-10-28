package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shumuzengxiao.smartcattle.domain.*;
import com.shumuzengxiao.smartcattle.repository.*;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.HttpStatus;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import java.net.URI;
import java.net.http.*;
import java.time.*;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

@Service
public class CattleNewsService {
    public record KnowledgeCard(String id, String category, String title, String summary, String content, String sourceUrl) {}
    public record Feed(List<CattleArticle> articles, List<CattleNewsSource> sources, String dailyDate,
                       String dailyKnowledgeId, boolean refreshing, Instant generatedAt) {}
    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");
    private final CattleArticleRepository articles;
    private final CattleNewsSourceRepository sources;
    private final CattleNewsParser parser;
    private final ObjectMapper mapper;
    private final AtomicBoolean refreshing = new AtomicBoolean();
    private final ExecutorService worker = Executors.newSingleThreadExecutor(task -> {
        Thread thread = new Thread(task, "cattle-news-refresh"); thread.setDaemon(true); return thread;
    });
    private final HttpClient http = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).sslContext(newsTls()).connectTimeout(Duration.ofSeconds(4))
            .followRedirects(HttpClient.Redirect.NEVER).build();

    private static javax.net.ssl.SSLContext newsTls() {
        try {
            if (System.getProperty("os.name", "").startsWith("Windows")) {
                var roots = java.security.KeyStore.getInstance("Windows-ROOT");
                roots.load(null, null);
                var managers = javax.net.ssl.TrustManagerFactory.getInstance(javax.net.ssl.TrustManagerFactory.getDefaultAlgorithm());
                managers.init(roots);
                var context = javax.net.ssl.SSLContext.getInstance("TLS");
                context.init(null, managers.getTrustManagers(), null);
                return context;
            }
            return javax.net.ssl.SSLContext.getDefault();
        } catch (Exception unavailable) {
            try { return javax.net.ssl.SSLContext.getDefault(); }
            catch (java.security.NoSuchAlgorithmException failure) { throw new IllegalStateException(failure); }
        }
    }

    public CattleNewsService(CattleArticleRepository articles, CattleNewsSourceRepository sources,
                             CattleNewsParser parser, ObjectMapper mapper) {
        this.articles = articles; this.sources = sources; this.parser = parser; this.mapper = mapper;
    }

    @PostConstruct
    void initialize() throws Exception {
        try (var stream = new ClassPathResource("cattle-knowledge.json").getInputStream()) {
            for (KnowledgeCard card : mapper.readValue(stream, KnowledgeCard[].class)) {
                if (!articles.existsById(card.id())) {
                    articles.save(new CattleArticle(card.id(), "knowledge", card.category(), card.title(), card.summary(),
                            card.content(), "数牧增效养殖知识库", card.sourceUrl(), Instant.parse("2026-10-22T00:00:00Z")));
                }
            }
        }
        initializeSource("moa", "农业农村部畜牧兽医局", "https://xmsyj.moa.gov.cn/");
        initializeSource("nahs", "全国畜牧总站", "https://www.nahs.org.cn/");
    }

    private void initializeSource(String id, String name, String url) {
        if (!sources.existsById(id)) { sources.save(new CattleNewsSource(id, name, url)); }
    }

    @Scheduled(initialDelayString = "${app.news.initial-delay-ms:5000}", fixedDelayString = "${app.news.refresh-ms:1800000}")
    public void refresh() {
        if (!refreshing.compareAndSet(false, true)) { return; }
        worker.submit(() -> {
            try {
                for (CattleNewsSource source : sources.findAll()) {
                    try {
                        var request = HttpRequest.newBuilder(URI.create(source.getUrl())).timeout(Duration.ofSeconds(10))
                                .header("User-Agent", "ShumuZengxiao/1.0 (public cattle news index)").GET().build();
                        var response = http.send(request, HttpResponse.BodyHandlers.ofByteArray());
                        if (response.statusCode() != 200 || response.body().length > 2_000_000) {
                            throw new IllegalStateException("Source unavailable");
                        }
                        String html;
                        try (var stream = new java.io.ByteArrayInputStream(response.body())) {
                            html = org.jsoup.Jsoup.parse(stream, null, source.getUrl()).html();
                        }
                        List<CattleArticle> incoming = parser.parse(html, source.getUrl(), source.getName(), LocalDate.now(ZONE));
                        if (incoming.isEmpty()) { throw new IllegalStateException("No matching articles"); }
                        articles.saveAll(incoming);
                        source.update(true, incoming.size());
                    } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt(); source.update(false, 0); break;
                    } catch (Exception unavailable) { source.update(false, 0); }
                    sources.save(source);
                }
            } finally { refreshing.set(false); }
        });
    }

    public Feed feed() {
        List<CattleArticle> cards = articles.findByKindOrderByIdAsc("knowledge");
        LocalDate day = LocalDate.now(ZONE);
        String dailyId = cards.isEmpty() ? "" : cards.get(Math.floorMod(day.toEpochDay(), cards.size())).getId();
        return new Feed(articles.findTop150ByOrderByPublishedAtDescIdAsc(), sources.findAll(), day.toString(), dailyId,
                refreshing.get(), Instant.now());
    }

    public CattleArticle article(String id) {
        return articles.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "资讯不存在"));
    }

    @PreDestroy
    void close() { worker.shutdownNow(); }
}
