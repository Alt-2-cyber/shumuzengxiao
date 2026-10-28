package com.shumuzengxiao.smartcattle.service;

import org.junit.jupiter.api.Test;
import java.time.LocalDate;
import static org.assertj.core.api.Assertions.assertThat;

class CattleNewsParserTest {
    private final CattleNewsParser parser = new CattleNewsParser();
    @Test
    void keepsDatedCattleArticlesDeduplicatesAndRejectsExternalFutureAndUnrelatedLinks() {
        String html = """
                <a href='./jcyj/202610/t20261020_123.htm'>10月第2周畜产品和饲料集贸市场价格情况</a>
                <a href='./jcyj/202610/t20261020_123.htm'>10月第2周畜产品和饲料集贸市场价格情况</a>
                <a href='./xw/202610/t20261019_124.htm' title='肉牛饲养管理培训通知'>肉牛饲养...</a>
                <a href='https://evil.test/xw/202610/t20261019_125.htm'>肉牛饲养管理培训通知</a>
                <a href='./xw/202710/t20271019_126.htm'>未来肉牛饲养管理培训通知</a>
                <a href='./xw/202610/t20261019_127.htm'>生猪饲料技术推广通知</a>
                <a href='./xw/202610/t20261019_128.htm'>人员招聘考试通知公告</a>
                <a href='javascript:alert(1)'>肉牛技术推广通知公告</a>
                """;
        var articles = parser.parse(html, "https://xmsyj.moa.gov.cn/", "畜牧兽医局", LocalDate.of(2026, 10, 22));
        assertThat(articles).hasSize(2);
        assertThat(articles.get(0).getCategory()).isEqualTo("market");
        assertThat(articles.get(0).getPublishedDate()).isEqualTo("2026-10-20");
        assertThat(articles.get(1).getTitle()).isEqualTo("肉牛饲养管理培训通知");
        assertThat(articles.get(0).getId()).isEqualTo(parser.parse(html, "https://xmsyj.moa.gov.cn/", "畜牧兽医局", LocalDate.of(2026, 10, 22)).get(0).getId());
        assertThat(articles.get(0).getContent()).doesNotContain("亿元", "增长率");
    }

    @Test
    void usesStructuredTitleSpanWithoutTheListDateAndSkipsTruncatedHeadlines() {
        String html = """
                <a href='/xw/202610/t20261021_1.htm'><span class='news-left'>肉牛口蹄疫防控知识</span><span>10-21</span></a>
                <a href='/xw/202610/t20261020_2.htm'>肉牛饲养...</a>
                <a href='/xw/202613/t20261340_3.htm'>错误日期肉牛资讯</a>
                """;
        var articles = parser.parse(html, "https://www.nahs.org.cn/", "全国畜牧总站", LocalDate.of(2026, 10, 22));
        assertThat(articles).hasSize(1);
        assertThat(articles.get(0).getTitle()).isEqualTo("肉牛口蹄疫防控知识");
        assertThat(articles.get(0).getCategory()).isEqualTo("health");
    }
}
