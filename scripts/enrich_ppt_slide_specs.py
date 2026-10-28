#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add structured slide_spec data for the Shumuzengxiao image2 PPT plan."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "report_assets"


def asset(name: str) -> str:
    return str((ASSETS / name).resolve()).replace("\\", "/")


def text_elem(content: str, kind: str = "text", position: str = "", style: str = "") -> dict:
    item = {"type": kind, "content": content}
    if position:
        item["position"] = position
    if style:
        item["style"] = style
    return item


def ext_image(source: str, position, detail: str = "critical", fit: str = "contain") -> dict:
    return {
        "type": "external_image",
        "source": asset(source),
        "position": position,
        "fit": fit,
        "slot_strategy": "fit-within",
        "tailor_to_asset": True,
        "detail_level": detail,
        "padding": 0.004,
        "bleed": 0.0,
        "outline_width": 0,
        "skeleton_canvas_fill": "transparent",
        "skeleton_fill": "transparent",
        "skeleton_shape": "corners",
        "skeleton_outline_width": 3,
    }


def spec(layout: str, elements: dict, page_type: str = "content") -> dict:
    return {
        "page_type": page_type,
        "layout": layout,
        "elements": elements,
    }


SPECS = {
    1: spec(
        "封面页，中央大标题，右侧/背景融合现代智能牛舍 AI 场景图，使用深色数据流装饰。",
        {
            "title": text_elem("数牧增效智能牛舍监测平台", "title", "居中偏左，超大标题，白色与青色强调"),
            "subtitle": text_elem("ESP32-S3 + MaixCam + 多模态 AI + Web/鸿蒙/微信小程序", "subtitle", "标题下方，两行以内"),
            "hero": {
                "type": "image_reference",
                "source": asset("ai-generated-smart-barn.png"),
                "mode": "reference",
                "description": "仅作为智能牛舍视觉参考，不作为真实截图后贴。",
            },
            "metrics": text_elem("端侧采集 | 边缘推理 | 云端治理 | 多端协同", "tagline", "页面底部，四段式技术标签"),
        },
        "cover",
    ),
    2: spec(
        "左侧背景问题展开，右侧智能牛舍剖面信息图，三张问题卡片加一个价值结论。",
        {
            "title": text_elem("项目背景：养殖现场从经验驱动走向数据驱动", "title", "左上角"),
            "problem_1": text_elem("巡检不连续：夜间、离岗、跨棚区时异常容易漏检", "card"),
            "problem_2": text_elem("异常发现滞后：环境、行为、声音变化缺少联合判断", "card"),
            "problem_3": text_elem("证据难追溯：缺少数据、截图、模型版本和人工确认链路", "card"),
            "value": text_elem("项目目标：用低成本硬件和平台化软件形成连续监测、主动预警、闭环处置。", "summary", "底部结论条"),
        },
    ),
    3: spec(
        "政策方向在上、市场痛点在下，形成政策驱动和落地问题的二维矩阵。",
        {
            "title": text_elem("国家政策与市场痛点：数字畜牧的现实入口", "title", "左上角"),
            "policy": text_elem("政策方向：数字农业、智慧畜牧、疫病防控、绿色养殖、农业基础设施升级", "axis", "上半区横向轴"),
            "pain": text_elem("市场痛点：人工成本高、响应慢、设备孤岛、AI 成本高、弱网场景难维护", "matrix", "下半区痛点矩阵"),
            "entry": text_elem("切入点：环境监测 + 多模态预警 + 多端协同，先解决可部署、可验证、可扩展。", "callout", "右下角强调"),
        },
    ),
    4: spec(
        "左侧短要点，右侧大面积真实系统架构图，突出端、边、云、服协同闭环。",
        {
            "title": text_elem("系统总体架构：端、边、云、服协同闭环", "title", "左上角窄栏"),
            "subtitle": text_elem("端侧采集、边缘推理、云端治理、多端应用、服务复盘", "subtitle", "标题下方"),
            "points": text_elem("ESP32-S3 负责环境与执行器；MaixCam 负责边缘视觉；Spring Boot 统一接入数据和命令；Web/鸿蒙/小程序共享同一后端。", "bullets", "左侧文字栏"),
            "architecture": ext_image("architecture-diagram.png", [0.43, 0.13, 0.52, 0.74]),
        },
    ),
    5: spec(
        "左侧硬件模块说明，右侧真实硬件拓扑图，底部给出接口扩展方向。",
        {
            "title": text_elem("硬件系统设计：低成本节点支撑连续采集", "title", "左上角"),
            "core": text_elem("主控：ESP32-S3 承担 Wi-Fi、采集、控制与协议通信；MaixCam 承担视觉推理；INMP441 采集声音事件。", "body", "左侧主体文字"),
            "sensors": text_elem("感知：温湿度、氨气、光照、烟雾；执行：风扇、雾化、声光报警、抓拍。", "body", "左侧第二段"),
            "extension": text_elem("扩展：水位、料槽、门磁、定位、更多继电器通道。", "tagline", "底部"),
            "hardware": ext_image("hardware-topology.png", [0.44, 0.14, 0.50, 0.70]),
        },
    ),
    6: spec(
        "通信协议页，左侧时序流程，右侧真实 MQTT topic map，强调弱网、心跳和回执。",
        {
            "title": text_elem("边缘固件与通信协议：从采集到闭环控制", "title", "左上角"),
            "flow": text_elem("采集 -> 预处理 -> 阈值/推理 -> MQTT 上报 -> 后端入库 -> 告警策略 -> 命令下发 -> 执行回执", "process", "左侧纵向流程"),
            "protocol": text_elem("MQTT：高频遥测、心跳、离线缓存、命令回执；HTTP：配置、模型版本、管理接口。", "body", "左下角"),
            "mqtt": ext_image("mqtt-topic-map.png", [0.48, 0.16, 0.45, 0.62]),
        },
    ),
    7: spec(
        "多模态 AI 页，中心融合模型，右侧真实数据流与风险矩阵组合图。",
        {
            "title": text_elem("多模态 AI 算法：环境、视觉、声音、历史趋势融合", "title", "左上角"),
            "input": text_elem("输入：环境阈值、趋势变化、视觉事件、声音事件、人工复核记录", "body", "左侧上部"),
            "output": text_elem("输出：风险等级、证据链、处置建议；用于辅助巡检，不替代兽医诊断。", "body", "左侧下部"),
            "dataflow": ext_image("multimodal-dataflow.png", [0.42, 0.14, 0.26, 0.60]),
            "risk": ext_image("risk-scoring-matrix.png", [0.69, 0.14, 0.25, 0.60]),
        },
    ),
    8: spec(
        "后端与数据治理页，左侧 API/数据对象说明，右侧上下两个真实技术图。",
        {
            "title": text_elem("后端平台与数据治理：统一接入、统一建模、统一追溯", "title", "左上角"),
            "backend": text_elem("Spring Boot REST API 按业务域组织：环境、设备、视觉、音频、健康风险、告警、模型。", "body", "左侧第一段"),
            "governance": text_elem("治理重点：设备 ID、时间戳、模型版本、证据链、人工确认、审计复盘。", "body", "左侧第二段"),
            "api_map": ext_image("api-map.png", [0.43, 0.12, 0.24, 0.66]),
            "database": ext_image("database-er.png", [0.69, 0.12, 0.25, 0.66]),
        },
    ),
    9: spec(
        "Web 成果展示页，中心大面积真实截图拼图，四周用少量标签说明模块。",
        {
            "title": text_elem("Web 平台成果展示：一屏协同监测、分析与控制", "title", "左上角"),
            "summary": text_elem("驾驶舱聚合存栏、设备、告警、趋势、边缘 FPS 和 3D 牛舍态势；环境、健康、设备、模型页面按业务域展开。", "body", "左侧短说明"),
            "labels": text_elem("驾驶舱 | 环境监测 | 健康风险 | 设备控制 | 模型管理", "tagline", "底部标签"),
            "web": ext_image("web-contact-sheet.png", [0.35, 0.13, 0.60, 0.72], "critical"),
        },
    ),
    10: spec(
        "移动端成果展示页，右侧真实鸿蒙 APP 拼图，左侧是移动巡检闭环流程。",
        {
            "title": text_elem("鸿蒙 APP 与微信小程序成果展示：移动端巡检与告警闭环", "title", "左上角"),
            "flow": text_elem("接收告警 -> 查看证据 -> 确认状态 -> 下发处置 -> 闭环记录", "process", "左侧流程"),
            "cooperation": text_elem("Web 负责总览分析，移动端负责即时查看和现场处置，微信小程序提供轻量协同入口。", "body", "左侧下部"),
            "hm": ext_image("hm-app-contact-sheet.png", [0.47, 0.10, 0.47, 0.76], "critical"),
        },
    ),
    11: spec(
        "创新点页，五个模块围绕主动防护闭环，右下叠加真实闭环图。",
        {
            "title": text_elem("创新点与技术优势：从监测工具升级为主动防护闭环", "title", "左上角"),
            "innovation_1": text_elem("端边云服协同：采集、推理、告警、处置、复盘、迭代完整闭环", "card"),
            "innovation_2": text_elem("多模态融合：环境 + 视觉 + 声音 + 历史趋势 + 人工复核", "card"),
            "innovation_3": text_elem("低成本可部署：ESP32-S3 与 MaixCam 降低试点门槛", "card"),
            "innovation_4": text_elem("证据链可追溯：数据、截图、模型版本、人工确认共同留痕", "card"),
            "innovation_5": text_elem("多端协同：Web、鸿蒙 APP、微信小程序共享同一后端", "card"),
            "closed_loop": ext_image("alarm-closed-loop.png", [0.61, 0.48, 0.31, 0.32], "high"),
        },
    ),
    12: spec(
        "应用、成果和未来计划的数据页，左侧场景，右侧路线图，底部真实部署与验收图。",
        {
            "title": text_elem("应用场景、阶段成果与未来计划", "title", "左上角"),
            "scenarios": text_elem("场景：中小牛舍巡检、规模场分区监测、环境联动、疫病风险早筛、教学实训、示范基地展示。", "body", "左侧上部"),
            "achievements": text_elem("阶段成果：前后端原型、Web 可视化、鸿蒙 APP、微信小程序、硬件拓扑、AI 训练流程、技术报告。", "body", "左侧中部"),
            "future": text_elem("未来：真实牛舍试点、传感器标定、样本扩充、OTA、边缘推理优化、告警策略验证、数据安全增强。", "body", "左侧下部"),
            "deploy": ext_image("deployment-layout.png", [0.47, 0.15, 0.22, 0.56], "high"),
            "test": ext_image("testing-acceptance-matrix.png", [0.71, 0.15, 0.23, 0.56], "high"),
        },
        "data",
    ),
    13: spec(
        "结尾页，中心结论大字，背景抽象端边云服闭环和现代牛舍轮廓。",
        {
            "title": text_elem("让牛舍风险更早被看见、被确认、被处置", "title", "居中超大标题"),
            "summary": text_elem("数牧增效把连续采集、边缘分析、云端治理、多端协同和现场处置连接成可落地的多模态 AI 主动防护体系。", "subtitle", "标题下方，2 行以内"),
            "footer": text_elem("数牧增效智能牛舍监测平台 | 技术汇报", "footer", "底部居中"),
        },
        "data",
    ),
}


def main() -> None:
    plan_path = ROOT / "slides_plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Missing {plan_path}")

    data = json.loads(plan_path.read_text(encoding="utf-8"))
    for slide in data.get("slides", []):
        num = int(slide["slide_number"])
        if num in SPECS:
            slide["slide_spec"] = SPECS[num]
            slide["page_type"] = SPECS[num].get("page_type", slide.get("page_type", "content"))

    data["total_slides"] = len(data.get("slides", []))
    plan_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] enriched {plan_path} with {len(SPECS)} slide specs")


if __name__ == "__main__":
    main()
