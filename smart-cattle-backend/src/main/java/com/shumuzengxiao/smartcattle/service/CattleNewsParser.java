package com.shumuzengxiao.smartcattle.service;

import com.shumuzengxiao.smartcattle.domain.CattleArticle;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Element;
import org.springframework.stereotype.Component;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.regex.Pattern;

@Component
public class CattleNewsParser {
    private static final Pattern ARTICLE_DATE = Pattern.compile("/\\d{6}/t(\\d{8})_\\d+\\.html?$");
    private static final Pattern RELEVANT = Pattern.compile("牛|奶业|奶农|畜产品|饲料|饲草|牧草|反刍|口蹄疫|动物疫情|动物检疫|畜禽粪污");
    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");

    public List<CattleArticle> parse(String html, String sourceUrl, String sourceName, LocalDate today) {
        Map<String, CattleArticle> articles = new LinkedHashMap<>();
        String host = URI.create(sourceUrl).getHost();
        for (Element anchor : Jsoup.parse(html, sourceUrl).select("a[href]")) {
            String url = anchor.absUrl("href");
            try {
                URI uri = URI.create(url);
                if (!"https".equals(uri.getScheme()) || !host.equals(uri.getHost()) || uri.getRawQuery() != null) { continue; }
                var matcher = ARTICLE_DATE.matcher(uri.getPath());
                if (!matcher.find()) { continue; }
                LocalDate date = LocalDate.parse(matcher.group(1), DateTimeFormatter.BASIC_ISO_DATE);
                if (date.isAfter(today)) { continue; }
                String title = anchor.attr("title").trim();
                if (title.isEmpty()) {
                    Element titleElement = anchor.selectFirst(".news-left");
                    title = titleElement == null ? anchor.text().trim() : titleElement.text().trim();
                }
                if (title.length() < 6 || title.length() > 240 || title.contains("...") || title.contains("…")) { continue; }
                if (!RELEVANT.matcher(title).find()) { continue; }
                if (title.matches(".*[猪鸡鸭鹅].*") && !title.matches(".*[牛奶].*")) { continue; }
                String category = categoryFor(title);
                String content = switch (category) {
                    case "market" -> "行情资讯用于了解行业变化。比较价格时，请同时核对地区、品种、统计时间和计价单位。\n\n完整数据与统计口径见原发布页。";
                    case "health" -> "防疫与检疫要求应结合原文适用范围、当地规定和兽医意见执行。\n\n具体措施与生效时间见原发布页。";
                    default -> "本条为公开行业资讯索引，保留原发布机构、日期和原文地址。\n\n政策适用范围、技术细节和原始附件见发布页。";
                };
                articles.put(url, new CattleArticle(idFor(url), "news", category, title, "", content,
                        sourceName, url, date.atStartOfDay(ZONE).toInstant()));
            } catch (IllegalArgumentException | DateTimeException invalid) {
                // Ignore malformed links without discarding the rest of a publisher's page.
            }
        }
        return articles.values().stream().sorted(Comparator.comparing(CattleArticle::getPublishedAt).reversed()).limit(40).toList();
    }

    static String categoryFor(String title) {
        if (title.matches(".*(价格|行情|市场|成本).*")) { return "market"; }
        if (title.matches(".*(疫情|疫病|口蹄疫|检疫|防疫|兽医|消毒).*")) { return "health"; }
        if (title.matches(".*(粪污|环保|环境|通风|高温).*")) { return "environment"; }
        if (title.matches(".*(饲料|饲草|牧草|营养|反刍).*")) { return "nutrition"; }
        return "industry";
    }

    static String idFor(String url) {
        try {
            return "news_" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(url.getBytes(StandardCharsets.UTF_8))).substring(0, 32);
        } catch (java.security.NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
    }
}
