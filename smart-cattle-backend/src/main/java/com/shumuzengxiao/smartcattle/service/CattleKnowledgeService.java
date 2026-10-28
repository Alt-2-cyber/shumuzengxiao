package com.shumuzengxiao.smartcattle.service;

import com.shumuzengxiao.smartcattle.dto.MobileSupport.Answer;
import com.shumuzengxiao.smartcattle.dto.MobileSupport.Reference;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class CattleKnowledgeService {
    private record Topic(List<String> keywords, String category, String content, Reference reference) {}

    private static final List<Topic> TOPICS = List.of(
            new Topic(List.of("口蹄", "水疱", "流涎"), "health",
                    "出现口腔或蹄部水疱、流涎并伴跛行时，应作为疑似传染病线索及时处理。\n"
                            + "1. 暂停相关牛只调运，隔离可疑牛只，减少人员和器具交叉接触。\n"
                            + "2. 联系当地兽医或动物防疫机构，按当地要求报告并安排采样。\n"
                            + "3. 记录耳标、首发时间、同栏发病数量、体温和病灶照片。\n"
                            + "声音、姿态和照片都不能单独确诊口蹄疫，需由兽医结合实验室检测判断。",
                    new Reference("WOAH：口蹄疫", "https://www.woah.org/en/disease/foot-and-mouth-disease/")),
            new Topic(List.of("跛行", "蹄", "腿", "走路", "加速度"), "health",
                    "跛行先从现场步态和蹄部检查开始。\n"
                            + "1. 在平整、防滑通道观察连续行走，记录负重不对称、背部弓起和步幅变化。\n"
                            + "2. 保存耳标及视频，对照该牛平日活动量，检查蹄部肿胀、外伤和地面湿滑。\n"
                            + "3. 持续不愿负重、剧痛或伴发热时，尽快请兽医检查。\n"
                            + "脖子、背部和腿部 ADXL345 能提供活动线索，但传感器移位、静卧和地面差异也会影响结果；不能直接判定病因。",
                    new Reference("MSD 兽医手册：牛跛行", "https://www.msdvetmanual.com/musculoskeletal-system/lameness-in-cattle/overview-of-lameness-in-cattle")),
            new Topic(List.of("咳", "呼吸", "声音", "声纹", "鼻液"), "health",
                    "咳嗽和呼吸异常需要结合个体体征与牛舍环境。\n"
                            + "1. 记录咳嗽发生时间、频次，保存原始音频，标记是否混入风扇或机械噪声。\n"
                            + "2. 观察静息呼吸、鼻眼分泌物、精神、采食及实际测得的体温。\n"
                            + "3. 检查通风、粉尘、氨气趋势及同栏是否也有症状。呼吸费力、站立困难等情况需立即联系兽医。\n"
                            + "INMP441 的声音异常提示不能区分具体病原，也不能替代兽医诊断。",
                    new Reference("MSD 兽医手册：牛呼吸道疾病", "https://www.msdvetmanual.com/respiratory-system/respiratory-diseases-of-cattle")),
            new Topic(List.of("温度", "体温", "发热", "红外", "b-1", "b1"), "health",
                    "先区分体表温度、环境温度和核心体温。\n"
                            + "1. B-1 红外模块测得的是目标表面温度，受距离、毛发、日照、风和测量位置影响。\n"
                            + "2. 固定测量部位和距离，记录环境温度并与该牛相同条件下的历史值比较。\n"
                            + "3. 发现持续升高且伴采食减少、精神差等表现时，请由人员按兽医指导复核核心体温。\n"
                            + "请提供测量部位、数值、持续时间和伴随症状，单次红外温度不能用于确诊疾病。",
                    new Reference("MSD 兽医手册", "https://www.msdvetmanual.com/")),
            new Topic(List.of("热应激", "闷热", "通风", "风扇", "氨气", "mq", "湿度"), "equipment",
                    "牛舍环境异常应同时核对传感器和现场。\n"
                            + "1. 检查温湿度、饮水和牛只喘气情况，按现场条件改善遮阴与通风。\n"
                            + "2. MQ 模块先完成预热和标定，未标定的模拟值不能直接当作准确 ppm 浓度。\n"
                            + "3. 风扇不转时，断电检查额定供电、独立电源、继电器常开/公共端和控制接地。不要让风扇由 ESP32 的 GPIO 直接供电。\n"
                            + "任何自动联动都应保留人工检查，确认设备实际运转。",
                    new Reference("FAO：畜牧生产与动物健康", "https://www.fao.org/animal-production-health/en/")),
            new Topic(List.of("采食", "反刍", "饲料", "营养", "饮水", "腹泻", "瘤胃"), "nutrition",
                    "采食或反刍减少时，先记录变化再查原因。\n"
                            + "1. 核对饮水供应、饲料是否变质、近期配方或投喂时间是否改变。\n"
                            + "2. 记录耳标、持续时间、粪便、腹围、精神及同栏牛只情况，和该牛平日表现比较。\n"
                            + "3. 持续拒食、明显腹胀、脱水或不能起立时应及时请兽医处理。\n"
                            + "活动传感器对反刍的推断需经现场标注验证；请提供日粮和症状后再讨论饲养调整，不宜仅凭行为标签用药。",
                    new Reference("FAO：畜牧生产与动物健康", "https://www.fao.org/animal-production-health/en/")),
            new Topic(List.of("离线", "wifi", "联网", "esp32", "接线", "传感器", "数据", "摄像头"), "equipment",
                    "先按供电、连接、采集、上传的顺序排查。\n"
                            + "1. 确认 ESP32-S3 和 MaixCAM 电源稳定，所有模块按额定电压供电、共地。\n"
                            + "2. I2C 检查地址冲突、SDA/SCL 与上拉；三个 ADXL345 需要独立总线或复用器，不能直接以同一地址挂同一总线。\n"
                            + "3. 检查串口日志、Wi-Fi 地址、服务器地址与最后上报时间；数据库中旧的在线状态不等于当前在线。\n"
                            + "4. 小程序真机需配置可访问的 HTTPS 服务域名；手机和电脑的 localhost 不是同一台机器。",
                    new Reference("Espressif：ESP32-S3 文档", "https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/"))
    );

    public Answer answer(String question) {
        String normalized = question.toLowerCase(java.util.Locale.ROOT);
        Topic best = null;
        int bestScore = 0;
        for (Topic topic : TOPICS) {
            int score = (int) topic.keywords().stream().filter(normalized::contains).count();
            if (score > bestScore) { best = topic; bestScore = score; }
        }
        if (best != null) {
            return new Answer(best.content(), "knowledge", "养殖巡检知识库 V1.0", "", best.category(), List.of(best.reference()));
        }
        return new Answer("请补充牛只耳标、异常开始时间、采食饮水、活动变化以及已测量的体温或环境数据。\n"
                + "可以先咨询：跛行观察、咳嗽记录、红外测温、牛舍通风、采食反刍或设备离线。\n"
                + "当前知识库没有足够依据回答这条问题，可将问题转交专家咨询，并保留现场观察记录。",
                "knowledge", "养殖巡检知识库 V1.0", "", "other", List.of());
    }
}
