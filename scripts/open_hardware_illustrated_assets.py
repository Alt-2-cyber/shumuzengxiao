# -*- coding: utf-8 -*-
"""Original diagrams and traceable screenshot preparations for the illustrated report."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_open_hardware_submission import COL, arrow, img_text, node

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/open_hardware_submission_illustrated_20261026"
WORK = OUT / "work"
ASSETS = WORK / "assets"
SCREENSHOTS = {
    "dashboard": "report_assets/web-dashboard.png",
    "environment": "report_assets/web-environment.png",
    "behavior": "smart-cattle-frontend/output/playwright/behavior-desktop.png",
    "device": "smart-cattle-frontend/output/playwright/device-controls-final.png",
    "vision_ui": "output/playwright/vision-page.png",
    "audio_ui": "output/playwright/audio-select-contrast.png",
    "clinical_ui": "output/playwright/clinical-workflow.png",
    "release_ui": "output/playwright/models-release-ledger-desktop.png",
    "mobile_behavior": "smart-cattle-frontend/output/playwright/behavior-mobile-final.png",
    "mobile_clinical": "output/playwright/clinical-mobile-actual.png",
    "mobile_release": "output/playwright/models-release-ledger-mobile.png",
    "hm_mobile": "report_assets/hm-app-2.png",
}

CROPS = {
    "dashboard": (282, 0, 1440, 1000),
    "environment": (282, 0, 1440, 1000),
    "behavior": (282, 0, 1440, 1115),
    "device": (282, 0, 1440, 1000),
    "vision_ui": (282, 0, 1440, 1130),
    "audio_ui": (282, 0, 1440, 1000),
    "clinical_ui": (310, 0, 1280, 950),
    "release_ui": (282, 0, 1440, 1000),
    "mobile_clinical": (0, 0, 360, 844),
}


def inventory():
    WORK.mkdir(parents=True, exist_ok=True)
    items = list(SCREENSHOTS.items())
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
    rows = []
    for start in range(0, len(items), 6):
        sheet = Image.new("RGB", (1800, 1190), "#DFE7E1")
        draw = ImageDraw.Draw(sheet)
        for i, (name, rel) in enumerate(items[start:start + 6]):
            source = ROOT / rel
            image = Image.open(source).convert("RGB")
            rows.append({"name": name, "source": rel, "size": list(image.size)})
            xx, yy = 15 + (i % 2) * 900, 42 + (i // 2) * 395
            draw.text((xx, yy - 31), f"{name}  {image.width}×{image.height}", font=font, fill="#182B22")
            image.thumbnail((870, 345))
            sheet.paste(image, (xx, yy))
        sheet.save(WORK / f"screenshot-inventory-{start // 6 + 1}.jpg", quality=92)
    (WORK / "screenshot-inventory.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False))


def canvas(name, height=800):
    image = Image.new("RGB", (1800, height), "#F5F8F6")
    return image, ImageDraw.Draw(image)


def save(image, name):
    ASSETS.mkdir(parents=True, exist_ok=True)
    image.save(ASSETS / (name + ".png"))


def diagram_chain(name, titles, bodies, note, colors=None):
    image, draw = canvas(name, 650)
    count = len(titles)
    gap = 46
    width = (1700 - gap * (count - 1)) // count
    colors = colors or ["green", "teal", "green", "gold", "teal"]
    for i, (title, body) in enumerate(zip(titles, bodies)):
        xx = 50 + i * (width + gap)
        node(draw, (xx, 85, xx + width, 460), title, body, colors[i % len(colors)], title_size=38, body_size=33)
        if i < count - 1:
            arrow(draw, [(xx + width + 5, 270), (xx + width + gap - 5, 270)], colors[i % len(colors)])
    img_text(draw, note, 90, 535, 1620, 34, color=COL["muted"], align="center")
    save(image, name)


def custom_diagrams():
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name in ("architecture", "reliability", "vision"):
        shutil.copy2(ROOT / "outputs/open_hardware_submission_20261026/work/assets" / (name + ".png"), ASSETS / (name + ".png"))
    diagram_chain("usage_flow", ["查看状态", "核对证据", "现场复核", "控制与留痕"], ["先看节点健康\n与数据时间", "原件与牛号\n模型及版本", "查看同一动物\n补充检查记录", "执行器回执\n处理记录与复测"], "图示为使用流程  环境控制与临床复核分别授权")
    diagram_chain("environment_flow", ["读取与自检", "条件判断", "本地执行", "平台核对"], ["温湿度与光照\n缺件显示不可用", "仅使用有效输入\n按规则触发", "低压驱动与风扇\n声光状态反馈", "查看命令回执\n对照后续遥测"], "MQ 等可选模块接好并标定后才启用  具体阈值由现场确认")
    diagram_chain("audio_pipeline", ["声音输入", "质量与窗口", "特征提取", "研究判别"], ["INMP441 I2S\n原始采集 16 kHz", "有效覆盖与补零\n静音可拒识", "时域与频域特征\n记录预处理版本", "保留事件分数\n原件回放与复核"], "现有固件与研究分类器分别验收  研究分数不等于疾病结论")
    diagram_chain("archive_flow", ["采集会话", "原件归档", "人工审核", "训练清单"], ["动物与设备编号\n时间和会话 ID", "图片 WAV NDJSON\n服务器重算哈希", "标签与依据\n操作人和时间", "来源及哈希\n分组与许可"], "原件  事件  审核记录  模型版本通过标识符关联")
    diagram_chain("release_flow", ["训练复核", "登记复核", "服务端核验", "批准或撤回"], ["数据来源与签核\n分组验证和模型卡", "工具重读档案\n比对训练血缘", "事务内重算指纹\n不一致则拒绝", "新版本不可覆盖\n保留撤回依据"], "当前三次血缘核验适用于已实现的声音与跛行发布路径")
    diagram_chain("contribution_flow", ["提出问题", "提交变更", "复现与评审", "版本发布"], ["Issue 复现步骤\n最小日志与版本", "独立分支与 PR\n最小修改范围", "测试与兼容性\n硬件变更附验收", "变更日志和哈希\n升级与回退说明"], "开源贡献制度为拟定流程  公开后以真实仓库活动为依据")
    diagram_chain("pilot_flow", ["台架检查", "单栏观察", "人工对照", "复测决策"], ["电源 模块 ID\n低压负载与日志", "按统一时间记录\n标出断流与维护", "独立巡查与视频\n确认参考标准", "修复问题再测试\n达标再扩大点位"], "24 小时台架与 2 至 4 周观察为拟定计划  尚非已完成试点结果")
    diagram_chain("case_flow", ["发现线索", "寻找证据", "现场检查", "记录与复测"], ["环境或活动偏移\n先核对数据有效", "牛号与事件时间\n声音或视觉原件", "人工巡查与复测\n必要时兽医检查", "设备命令与回执\n形成后续观察"], "教学说明案例  无具体患牛与实测发现时长  不作为已发生病例")

    image, draw = canvas("bus_topology", 850)
    node(draw, (60, 255, 650, 570), "牛身 ESP32-S3", "SPI 运动总线\nI2S 声音输入\nUART 与 I2C 分工", title_size=45, body_size=37)
    node(draw, (820, 60, 1735, 235), "三块 ADXL345  共用 SPI", "SCK40  MOSI41  MISO42  /  CS38  CS39  CS47", title_size=40, body_size=34)
    node(draw, (820, 290, 1735, 465), "INMP441  独立 I2S", "BCLK5  WS6  SD7  /  L-R 接 GND", "teal", 40, 34)
    node(draw, (820, 520, 1735, 695), "B-1 与 MAX30102", "B-1 接 ESP32 RX18/TX17  /  MAX 使用 I2C8/9", "green", 40, 32)
    for yy in (150, 380, 610):
        arrow(draw, [(655, 415), (740, 415), (740, yy), (815, yy)], "teal")
    img_text(draw, "所有传感器按当前模块说明使用 3.3 V  信号共地  不混用旧演示板引脚", 90, 765, 1620, 34, color=COL["muted"], align="center")
    save(image, "bus_topology")

    image, draw = canvas("mounting", 650)
    draw.ellipse((500, 205, 1310, 450), fill="#D9E3DD", outline="#6B7F71", width=4)
    draw.polygon([(500, 245), (390, 220), (280, 260), (310, 380), (490, 365)], fill="#D9E3DD", outline="#6B7F71", width=4)
    draw.polygon([(370, 228), (380, 175), (415, 228)], fill="#D9E3DD", outline="#6B7F71", width=4)
    for xx in (565, 640, 1110, 1190):
        draw.rounded_rectangle((xx, 400, xx + 37, 530), radius=10, fill="#D9E3DD", outline="#6B7F71", width=3)
    draw.line([(1295, 265), (1390, 300), (1410, 390)], fill="#6B7F71", width=7)
    for x, y, title, tx, ty in [(490, 310, "颈部  朝向固定", 65, 80), (865, 230, "背部  稳定安装", 720, 65), (1145, 475, "腿部  线束防拉扯", 1280, 75)]:
        draw.ellipse((x - 22, y - 22, x + 22, y + 22), fill="#1D7054", outline="white", width=4)
        img_text(draw, title, tx, ty, 450, 39, True, COL["green"])
        arrow(draw, [(tx + 150, ty + 70), (tx + 150, ty + 105), (x, y - 30)])
    img_text(draw, "佩戴位置与固定方式示意  不是动物实测照片  安装需兼顾舒适  防水与维修", 65, 585, 1670, 32, color=COL["muted"], align="center")
    save(image, "mounting")

    image, draw = canvas("telemetry", 950)
    xs = [230, 670, 1120, 1570]
    for xx, title in zip(xs, ["ESP32 节点", "统一接入", "归档与状态", "Web 或移动端"]):
        draw.rounded_rectangle((xx - 180, 45, xx + 180, 130), radius=12, fill="#E3EFE9", outline="#1D7054", width=3)
        img_text(draw, title, xx - 165, 68, 330, 37, True, align="center")
        draw.line([(xx, 150), (xx, 805)], fill="#B8C8BF", width=4)
    for y, first, last, label in [(230, 0, 1, "HTTP 或 USB  一帧遥测"), (360, 1, 2, "校验身份  时间与模块状态"), (490, 2, 3, "查询与实时推送"), (620, 3, 1, "授权控制指令"), (745, 1, 0, "发送指令并等待回执")]:
        arrow(draw, [(xs[first], y), (xs[last], y)], "teal" if y < 600 else "green")
        img_text(draw, label, min(xs[first], xs[last]) + 15, y - 60, abs(xs[last] - xs[first]) - 30, 32, align="center")
    img_text(draw, "回执之后继续对照实际状态  连接状态与数据新鲜度分别判定", 90, 860, 1620, 34, color=COL["muted"], align="center")
    save(image, "telemetry")

    image, draw = canvas("deployment", 850)
    draw.rounded_rectangle((50, 70, 1080, 655), radius=15, fill="white", outline="#1D7054", width=4)
    img_text(draw, "单栏试点配置示意", 80, 95, 960, 43, True)
    for i in range(4):
        draw.rectangle((90 + i * 230, 240, 285 + i * 230, 430), fill="#ECF2EE", outline="#B2C7BA", width=3)
        img_text(draw, "牛只区域", 95 + i * 230, 305, 185, 33, align="center")
    node(draw, (80, 490, 540, 620), "环境节点", "靠近代表性监测位置", title_size=36, body_size=29)
    node(draw, (590, 490, 1045, 620), "视觉节点", "避开遮挡与直射逆光", "teal", 36, 29)
    node(draw, (1230, 125, 1745, 355), "现场主机与路由", "局域网地址\n后端 数据库与存储", "teal", 38, 34)
    node(draw, (1230, 475, 1745, 685), "管理与巡检", "电脑管理\n授权移动巡检", "green", 38, 34)
    arrow(draw, [(1090, 360), (1165, 360), (1165, 235), (1225, 235)], "teal")
    arrow(draw, [(1490, 360), (1490, 470)])
    img_text(draw, "点位数量  无线覆盖  供电与外壳须经现场勘查  图中不代表已建成牧场", 80, 770, 1640, 33, color=COL["muted"], align="center")
    save(image, "deployment")

    image, draw = canvas("license_layers", 650)
    labels = [("自研源码与硬件", "确定权利与拟定许可证", "green"), ("第三方代码与模型", "逐组件核对分发义务", "teal"), ("数据与媒体素材", "来源  署名与授权范围", "gold")]
    for i, (title, body, color) in enumerate(labels):
        node(draw, (70 + i * 575, 100, 580 + i * 575, 400), title, body + "\n保留版本和清单", color, 39, 35)
    img_text(draw, "源码许可不能代替数据授权  自研许可不能覆盖上游素材", 80, 515, 1640, 36, color=COL["muted"], align="center")
    save(image, "license_layers")

    image, draw = canvas("roadmap", 850)
    periods = ["0—1 月", "1—3 月", "3—6 月", "6—12 月", "12 月后"]
    tasks = ["恢复设备与采集", "开源发布与单栏试点", "独立分组数据与验证", "跨场测试及结构改进", "维护交接与合作扩展"]
    for i, period in enumerate(periods):
        img_text(draw, period, 540 + i * 240, 75, 220, 34, True, align="center")
        draw.line([(650 + i * 240, 140), (650 + i * 240, 730)], fill="#D4DFD8", width=3)
    for i, task in enumerate(tasks):
        yy = 180 + i * 112
        img_text(draw, task, 60, yy + 10, 440, 35, True)
        xx = 560 + i * 240
        draw.rounded_rectangle((xx, yy, xx + 180, yy + 70), radius=8, fill="#1D7054" if i % 2 == 0 else "#166F83")
    img_text(draw, "拟定里程碑  以实际验收与授权为推进条件  不承诺按时间自动启用疾病模型", 75, 775, 1650, 32, color=COL["muted"], align="center")
    save(image, "roadmap")

    image, draw = canvas("customer_paths", 780)
    for i, (title, body, color) in enumerate([
        ("天津仁爱学院", "拟对接教学实训\n节点搭建与数据实践\n课程案例与学生报告", "green"),
        ("天津大学相关团队", "拟对接研究验证\n任务定义与分组实验\n数据及成果使用授权", "teal"),
        ("中小牧场", "拟开展单栏试点\n连续采集与人工复核\n安装维护与使用反馈", "gold"),
    ]):
        node(draw, (55 + i * 585, 90, 575 + i * 585, 545), title, body, color, 39, 35)
    img_text(draw, "先确认需求与授权  再匹配交付物  合作状态以实际意向书或试点记录为准", 75, 655, 1650, 34, color=COL["muted"], align="center")
    save(image, "customer_paths")

    image, draw = canvas("testing_map", 650)
    entries = [("后端逻辑", "57 / 57", "green"), ("生命周期", "4 / 4", "teal"), ("串口工具", "4 / 4", "green"), ("音频契约", "17 / 17", "teal"), ("固件宿主", "6 / 6", "green")]
    for i, (title, result, color) in enumerate(entries):
        xx = 55 + i * 350
        draw.rounded_rectangle((xx, 90, xx + 295, 405), radius=12, fill="white", outline="#" + COL[color], width=4)
        img_text(draw, title, xx + 15, 130, 265, 37, True, align="center")
        img_text(draw, result, xx + 15, 240, 265, 48, True, COL[color], align="center")
    img_text(draw, "均为已执行的软件或宿主检查  不合并成现场准确率", 80, 465, 1640, 36, align="center")
    img_text(draw, "旧视觉测试桩导入失败另列已知问题  前端生产构建通过", 80, 540, 1640, 33, color=COL["muted"], align="center")
    save(image, "testing_map")


def screenshot_assets():
    ASSETS.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, rel in SCREENSHOTS.items():
        source = ROOT / rel
        image = Image.open(source).convert("RGB")
        crop = CROPS.get(name)
        if crop:
            image = image.crop(crop)
        output = ASSETS / (name + ".png")
        image.save(output)
        manifest.append({"asset": output.name, "source": rel, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "crop_xyxy": crop, "meaning": "historical development screenshot, not new field acceptance"})
    (WORK / "image-sources.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # Three phone screenshots are presented at their original proportions.
    image = Image.new("RGB", (1800, 1190), "#F5F8F6")
    draw = ImageDraw.Draw(image)
    for i, (name, label) in enumerate([("mobile_behavior", "移动网页  行为与状态"), ("hm_mobile", "鸿蒙原型  图片输入"), ("mobile_release", "移动网页  发布记录")]):
        im = Image.open(ASSETS / (name + ".png")).convert("RGB")
        im.thumbnail((530, 1025))
        xx = 45 + i * 590 + (530 - im.width) // 2
        yy = 105
        image.paste(im, (xx, yy))
        img_text(draw, label, 45 + i * 590, 25, 530, 35, True, align="center")
    save(image, "mobile_triptych")
    # The cover gets a restrained, informative diagram rather than a stock photograph.
    image, draw = canvas("cover_overview", 430)
    for i, (title, body, color) in enumerate([("现场节点", "环境  运动  声音", "green"), ("边缘与平台", "视觉事件  数据归档", "teal"), ("管理与复核", "控制回执  人工检查", "green")]):
        node(draw, (35 + i * 600, 30, 565 + i * 600, 335), title, body, color, 43, 37)
        if i < 2:
            arrow(draw, [(570 + i * 600, 180), (630 + i * 600, 180)], "teal")
    save(image, "cover_overview")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args()
    if args.inventory:
        inventory()
        return
    custom_diagrams()
    screenshot_assets()
    print(json.dumps({"asset_directory": str(ASSETS), "assets": len(list(ASSETS.glob('*.png')))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
