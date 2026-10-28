from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import httpx


DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1536x864"
DEFAULT_QUALITY = "high"
RETRY_STATUSES = {429, 500, 502, 503, 504, 522, 524}


@dataclass
class SlidePage:
    number: int
    title: str
    lines: list[str]


LAYOUTS = {
    1: "封面式：左侧超大品牌标题，右侧真实牛舍与全息数据中控台，底部细长发光信息栏。",
    2: "项目总览式：中心大型智慧牛舍平台屏幕，四周环绕 6 个半透明功能模块，底部一句战略总结。",
    3: "初心问题式：左侧数字巡检员主视觉，右侧上下两张数据图表卡和痛点条带。",
    4: "阶段演进式：横向时间轴从人工巡栏到多模态智能，背景是由旧牛舍逐渐过渡到数字牛舍。",
    5: "对比矩阵式：五列方案卡片并排，最后一列高亮牧云智舍，卡片之间用细发光分隔线。",
    6: "政策支撑式：深绿政策文件墙背景，三份发光文件卡片悬浮，右侧政策关键词云。",
    7: "市场规模式：大型环形市场图居中，四个增长场景分布四角，形成数据仪表盘。",
    8: "产业调研式：访谈地图与便签墙组合，左侧用户画像，右侧调研结论高亮框。",
    9: "痛点雷达式：中央红橙风险雷达圈，周围分布环境、视觉、声音、数据四类风险警示卡。",
    10: "研发路线式：2024-2025 横向发光里程碑轨道，节点配硬件、后端、视觉、移动端图标。",
    11: "解决方案架构式：一项技术在中心，二大平台左右托举，三大支撑和五步闭环形成环形流程。",
    12: "传感器驾驶舱式：左侧 ESP32-S3 节点与传感器，右侧实时数据表、滑动窗口和阈值曲线。",
    13: "边缘视觉式：牛只检测框、MaixCam、YOLO 模型管线和 INT8 部署路线组成纵深透视版式。",
    14: "声音融合式：声波频谱横贯页面，环境阈值、视觉事件、声音线索和历史趋势汇入风险等级。",
    15: "改进前后式：三组上下对照卡片，前后用发光箭头连接，右侧放试点验证目标。",
    16: "竞品象限式：四个竞品方案置于 2x2 矩阵，中心发光系统闭环突出牧云智舍。",
    17: "成果墙式：软件界面、证书、软著和专利占位卡组成荣誉墙，底部提醒按实际填写。",
    18: "创新证据链式：四个创新点以链路节点连接，背景显示检索关键词与技术网络。",
    19: "行业认可式：多角色反馈气泡环绕中心评价，引入教师、养殖户、农服机构和实训基地。",
    20: "养殖户反馈式：夜间牛舍与手机告警场景，左侧客户类型，右侧试点指标与价值。",
    21: "高校实训式：教室与牛舍数字孪生双场景分屏，四个教学应用以模块卡呈现。",
    22: "示范推广式：区域地图网络连接合作社、农服机构、设备渠道商，右侧接入设备列表。",
    23: "产业链地图式：上中下游三段横向供应链流，延伸服务作为底部 SaaS 服务带。",
    24: "商业模式飞轮式：产品销售、平台部署、SaaS 订阅、运维增值组成闭环飞轮。",
    25: "营销渠道式：展会、学术、定制、网络四个发光通道汇入品牌增长漏斗。",
    26: "测试检测式：实验室测试台与数据验收看板组合，硬件、传感器、算法、系统四区块。",
    27: "应用领域蜂巢式：五个蜂巢模块围绕智慧牛舍核心，生产、教学、示范、设备、数据并列。",
    28: "意向客户管线式：客户 A/B/C 三张客户卡从左到右推进，底部展示材料清单。",
    29: "财务预测式：三年增长阶梯与收入结构分层柱状图，旁边列出成本口径。",
    30: "融资计划式：资金分配环形图居中，五类用途围绕，底部融资逻辑和真实填写提示。",
    31: "媒体宣传式：多屏媒体墙，官网、公众号、短视频、展会海报组成传播矩阵。",
    32: "社会效益式：绿色养殖生态树，枝叶分别代表养殖户、动物健康、高校实训和农服标准化。",
    33: "创始人档案式：人物剪影与项目负责人信息卡，右侧职责、经验和荣誉材料分层。",
    34: "团队矩阵式：七个专业角色围绕项目核心，连线形成跨学科协同网络。",
    35: "导师支持式：五位指导角色以顾问席位排布，背景为实验室和牛舍双场景。",
    36: "专家顾问式：四类专家卡片环绕风险把关中心，底部真实姓名和成果提示。",
    37: "院校支持式：校园科研平台、课程资源、双创体系、场景资源组成四象限生态图。",
    38: "产教融合式：企业、学校、实训场景三端桥梁连接，突出实践育人和产学研联动。",
    39: "疑难解惑式：左侧问题风暴云，右侧解决路径阶梯，底部团队成长成果。",
    40: "反哺教育式：学校、学科、社会三圈同心扩散，配课堂实践和项目宣讲视觉。",
    41: "就业网络式：直接岗位和间接岗位双层节点图，岗位清单围绕项目试点扩散。",
    42: "发展规划式：2026-2030 五年路线图，产品市场逐年升级，终点是区域化智慧牛舍服务平台。",
    43: "封底式：全屏深绿科技牛舍远景，中间口号与品牌，底部政策和技术依据小字区。",
}


STYLE_PROMPT = """
整体风格：深绿色复杂科技农业海报图，适合作为 16:9 PPT 整页图片。
主色为深墨绿、森林绿、翡翠绿，辅以少量青绿色霓虹光、浅黄绿色重点字；画面要复杂、有层次，包含智慧牛舍、肉牛养殖、传感器节点、边缘 AI、云端平台、数据大屏、全息 HUD、网格地面、发光线路、风险预警图标等元素。
参考风格：深绿智慧农业展板、半透明玻璃卡片、发光科技边框、真实牛舍与未来感数字界面融合；不要复刻任何模板或已有页面构图。
文字要求：所有可见文字使用简体中文，标题必须清晰可读，优先保证大标题、关键短语、年份、百分比和技术词准确；允许只展示本页最核心短句，不要生成乱码、伪文字、无意义英文或水印。
字体要求：粗黑体标题，清晰无衬线正文，强对比白色/浅绿色文字；不要书法字，不要花体字。
画面比例：严格 16:9 横版宽屏，宽度明显大于高度，整页海报构图。
避免：不要白色空白模板感，不要浅绿色单调背景，不要卡通风，不要低清文字，不要网页 UI 水印，不要多余 logo，不要把牛画成其他动物。
"""


def parse_pages(text: str) -> list[SlidePage]:
    matches = list(re.finditer(r"^P(\d{2})\s+(.+?)\s*$", text, re.MULTILINE))
    pages: list[SlidePage] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        raw = text[start:end].strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        pages.append(SlidePage(number=int(match.group(1)), title=match.group(2).strip(), lines=lines))
    return pages


def compact_lines(page: SlidePage) -> list[str]:
    lines = page.lines[:]
    if page.number in {1, 43}:
        return lines[:8]
    compact: list[str] = []
    for line in lines:
        normalized = re.sub(r"\s+", " ", line).strip()
        if not normalized:
            continue
        if len(normalized) > 56:
            if "：" in normalized:
                label, value = normalized.split("：", 1)
                normalized = f"{label}：{value[:40]}"
            else:
                normalized = normalized[:54]
        compact.append(normalized)
        if len(compact) >= 7:
            break
    return compact


def build_prompt(page: SlidePage) -> str:
    copy_lines = compact_lines(page)
    visible_text = "\n".join(f"- {line}" for line in copy_lines)
    layout = LAYOUTS.get(page.number, "非重复信息图海报版式，和前后页面明显不同。")
    section_hint = "封面页" if page.number == 1 else "封底页" if page.number == 43 else "内容页"
    return f"""{STYLE_PROMPT}

现在生成第 {page.number:02d} 页，页面类型：{section_hint}。
本页标题：{page.title}
本页专属版式：{layout}

本页必须呈现的可见文字如下，只使用这些中文内容，不要自行添加其他长段文字：
大标题：{page.title}
关键内容：
{visible_text}

设计重点：
1. 第 {page.number:02d} 页要与其他页面版式明显不同，不能套用同一模板。
2. 文字和图形要融入同一张 image2 生成的海报中，不要留给后期排版的空白占位。
3. 内容层级清楚：页码/栏目弱化，大标题最醒目，关键内容做成卡片、图表、流程、仪表或地图。
4. 背景复杂但不压文字，文字区域使用深绿玻璃面板或半透明发光信息框增强可读性。
5. 画面应像高水平大学生创新创业路演 PPT 海报页，专业、科技、农业场景明确。
"""


def build_compact_prompt(page: SlidePage) -> str:
    copy_lines = compact_lines(page)[:4]
    visible_text = "、".join(line[:28] for line in copy_lines if line)
    section_hint = "封面页" if page.number == 1 else "封底页" if page.number == 43 else "内容页"
    return (
        f"16:9 横版 PPT 整页海报，深绿色复杂科技农业风格，{section_hint}，第 {page.number:02d} 页。"
        f"主题：{page.title}。可见简体中文短语：{page.title}、{visible_text}。"
        "画面：智慧牛舍、肉牛、传感器、边缘AI、云平台、数据大屏、发光线路、风险预警。"
        "深墨绿森林绿背景，青绿色霓虹，高级路演海报，文字清晰，布局与其他页不同。"
        "不要水印，不要英文，不要乱码，不要卡通。"
    )


def build_ultra_prompt(page: SlidePage) -> str:
    first_line = compact_lines(page)[0] if page.lines else page.title
    if len(first_line) > 24:
        first_line = first_line[:24]
    focuses = {
        4: "时间轴、旧牛舍到数字牛舍",
        8: "访谈地图、便签墙、用户画像",
        10: "研发里程碑、硬件节点、移动端",
        14: "声波频谱、多模态风险融合",
        15: "改进前后对比、三组箭头",
        16: "竞品矩阵、系统闭环中心",
        20: "夜间牛舍、手机告警、试用反馈",
        21: "高校实训、课堂、数字孪生牛舍",
        22: "区域地图、合作社、农服机构",
        23: "产业链地图、上中下游、SaaS服务",
        24: "商业模式飞轮、硬件、平台、订阅",
        25: "营销渠道、展会、短视频、增长漏斗",
        26: "测试台、验收看板、算法指标",
        27: "应用领域蜂巢、生产教学示范",
        28: "客户管线、三张客户卡",
        29: "财务预测、三年增长阶梯",
        30: "融资计划、资金分配环形图",
        31: "媒体矩阵、多屏宣传墙",
        32: "社会效益、绿色养殖生态树",
        33: "创始人档案、人物剪影",
        34: "团队协作网络、七个角色",
        35: "导师支持、顾问席位",
        36: "专家顾问、风险把关中心",
        37: "院校支持、四象限生态图",
        38: "产教融合、校企桥梁",
        39: "疑难解惑、问题云、解决阶梯",
        40: "反哺教育、三圈同心扩散",
        41: "就业网络、岗位节点图",
        42: "2026到2030路线图、市场升级",
        43: "封底、智慧牛舍远景、AI赋能",
    }
    focus = focuses.get(page.number, "智慧牛舍、数据大屏、发光信息图")
    return (
        f"16:9横版PPT整页海报，深绿色复杂科技农业风格。第{page.number:02d}页：{page.title}。"
        f"主题：{first_line}。画面包含{focus}、肉牛、传感器发光节点、云端数据线。"
        f"可见简体中文短语：{page.title}、{first_line}、牧云智舍。"
        "深墨绿森林绿背景，青绿色霓虹线条，半透明玻璃信息框，专业路演海报，文字清晰。"
        "不要水印，不要英文，不要乱码，不要卡通。"
    )


def parse_slide_selection(value: str | None) -> set[int] | None:
    if not value:
        return None
    selected: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            selected.update(range(int(start_s), int(end_s) + 1))
        else:
            selected.add(int(part))
    return selected


def extract_image_b64(data: dict) -> str:
    items = data.get("data")
    if not isinstance(items, list) or not items:
        raise RuntimeError("Response does not contain image data")
    first = items[0]
    if not isinstance(first, dict):
        raise RuntimeError("Unexpected image data format")
    b64_data = first.get("b64_json")
    if not isinstance(b64_data, str) or not b64_data:
        raise RuntimeError("Response does not contain b64_json image data")
    return b64_data


def parse_error_body(text: str) -> str:
    try:
        data = json.loads(text)
    except Exception:
        return text[:500]
    error = data.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or error.get("type") or text[:500])
    if isinstance(error, str):
        return error
    return text[:500]


async def generate_slide(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    size: str,
    quality: str,
    timeout: int,
    retries: int,
    page: SlidePage,
    out_path: Path,
    compact_prompt: bool = False,
    ultra_prompt: bool = False,
) -> dict:
    if ultra_prompt:
        prompt = build_ultra_prompt(page)
    elif compact_prompt:
        prompt = build_compact_prompt(page)
    else:
        prompt = build_prompt(page)
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "n": 1,
        "response_format": "b64_json",
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{base_url.rstrip('/')}/images/generations"
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=timeout)
        except httpx.RequestError as exc:
            last_error = f"network error: {exc}"
            if attempt < retries:
                await asyncio.sleep(2 * attempt)
                continue
            raise RuntimeError(last_error) from exc

        if response.status_code == 200:
            data = response.json()
            out_path.write_bytes(base64.b64decode(extract_image_b64(data)))
            return {
                "slide": page.number,
                "title": page.title,
                "path": str(out_path),
                "prompt": prompt,
                "ok": True,
            }

        message = parse_error_body(response.text)
        last_error = f"HTTP {response.status_code}: {message}"
        if response.status_code in RETRY_STATUSES and attempt < retries:
            await asyncio.sleep(5 * attempt)
            continue
        raise RuntimeError(last_error)
    raise RuntimeError(last_error or "request failed")


async def generate_all(args: argparse.Namespace) -> int:
    api_key = os.environ.get("IMAGE2_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Missing IMAGE2_API_KEY or OPENAI_API_KEY", file=sys.stderr)
        return 2

    source = Path(args.source)
    text = source.read_text(encoding="utf-8")
    pages = parse_pages(text)
    selected = parse_slide_selection(args.slides)
    if selected is not None:
        pages = [page for page in pages if page.number in selected]
    if args.limit:
        pages = pages[: args.limit]
    if not pages:
        print("No pages selected", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    image_dir = out_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "image2_manifest.json"
    progress_path = out_dir / "progress.jsonl"

    existing: dict[int, dict] = {}
    if manifest_path.exists():
        try:
            for item in json.loads(manifest_path.read_text(encoding="utf-8")).get("slides", []):
                existing[int(item["slide"])] = item
        except Exception:
            existing = {}

    results: list[dict] = []
    failures: list[dict] = []
    semaphore = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient() as client:
        async def worker(page: SlidePage) -> None:
            out_path = image_dir / f"slide-{page.number:02d}.png"
            if out_path.exists() and not args.force:
                item = existing.get(page.number) or {
                    "slide": page.number,
                    "title": page.title,
                    "path": str(out_path),
                    "prompt": build_prompt(page),
                    "ok": True,
                    "skipped": True,
                }
                results.append(item)
                print(f"[skip] P{page.number:02d} {page.title}", flush=True)
                return
            async with semaphore:
                print(f"[start] P{page.number:02d} {page.title}", flush=True)
                try:
                    item = await generate_slide(
                        client,
                        base_url=args.base_url,
                        api_key=api_key,
                        model=args.model,
                        size=args.size,
                        quality=args.quality,
                        timeout=args.timeout,
                        retries=args.retries,
                        page=page,
                        out_path=out_path,
                        compact_prompt=args.compact_prompt,
                        ultra_prompt=args.ultra_prompt,
                    )
                    results.append(item)
                    with progress_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"ok": True, "slide": page.number, "path": str(out_path)}, ensure_ascii=False) + "\n")
                    print(f"[done] P{page.number:02d} -> {out_path}", flush=True)
                except Exception as exc:
                    failure = {"slide": page.number, "title": page.title, "ok": False, "error": str(exc)}
                    failures.append(failure)
                    with progress_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(failure, ensure_ascii=False) + "\n")
                    print(f"[fail] P{page.number:02d}: {exc}", flush=True)

        await asyncio.gather(*(worker(page) for page in pages))

    results.sort(key=lambda item: int(item["slide"]))
    failures.sort(key=lambda item: int(item["slide"]))
    manifest = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(source),
        "base_url": args.base_url,
        "model": args.model,
        "size": args.size,
        "quality": args.quality,
        "slides": results,
        "failures": failures,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[manifest] {manifest_path}", flush=True)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--base-url", default=os.environ.get("IMAGE2_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--slides", default=None, help="Comma/range list, e.g. 1,3,5-7")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--compact-prompt", action="store_true", help="Use a shorter prompt to reduce proxy timeouts")
    parser.add_argument("--ultra-prompt", action="store_true", help="Use an ultra-short prompt for stubborn proxy timeouts")
    return asyncio.run(generate_all(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
