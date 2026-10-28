from __future__ import annotations

import hashlib
import json
import re
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

import build_cow_copyright_package as base
import build_cow_walkthrough_materials as walkthrough
from cow_copyright_content import APPS
from cow_manual_walkthrough_content import mobile_flows

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.run' / 'harmony-copyright-update-20261023'
CAPTURES = ROOT / '.run' / 'app-ui-20261023'
NAME = '数牧增效牛舍智能巡检与预警平台'
TARGET = Path(r'D:\table\软著申请\牛') / NAME
STAGE = WORK / '新版材料' / NAME


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(node):
    return [int(value) for value in re.findall(r'-?\d+', node['bounds'])]


def visible(node):
    x, y, right, bottom = bounds(node)
    return right > x and bottom > y and y >= 132 and bottom <= 2664


def node_text(nodes, text, kind=None):
    return next(node for node in nodes if node.get('text') == text and
                (kind is None or node.get('type') == kind) and visible(node))


def button_for(nodes, text):
    target = node_text(nodes, text)
    x, y, right, bottom = bounds(target)
    candidates = []
    for node in nodes:
        if node.get('type') != 'Button' or not visible(node):
            continue
        left, top, r, b = bounds(node)
        if left <= (x + right) / 2 <= r and top <= (y + bottom) / 2 <= b:
            candidates.append(node)
    return min(candidates, key=lambda node: (bounds(node)[2] - bounds(node)[0]) * (bounds(node)[3] - bounds(node)[1]))


def clickable_for(nodes, text):
    target = node_text(nodes, text)
    x, y, right, bottom = bounds(target)
    candidates = []
    for node in nodes:
        if node.get('clickable') != 'true' or not visible(node):
            continue
        left, top, r, b = bounds(node)
        if left <= (x + right) / 2 <= r and top <= (y + bottom) / 2 <= b:
            candidates.append(node)
    return min(candidates, key=lambda node: (bounds(node)[2] - bounds(node)[0]) * (bounds(node)[3] - bounds(node)[1]))


def load_capture(raw_name, key, specs):
    image = CAPTURES / f'{raw_name}.jpeg'
    layout = CAPTURES / f'{raw_name}-layout.json'
    nodes = json.loads(layout.read_text('utf-8'))
    width, height = Image.open(image).size
    marks = []
    for label, text, finder in specs:
        node = finder(nodes)
        rect = bounds(node)
        assert visible(node), (raw_name, text, rect)
        assert 0 <= rect[0] < rect[2] <= width and 0 <= rect[1] < rect[3] <= height
        marks.append(dict(label=str(label), text=text, rect=rect, widgetType=node['type'],
                          hierarchy=node.get('hierarchy', ''), enabled=node.get('enabled') == 'true'))
    return dict(key=key, file=str(image), layout=str(layout), marks=marks,
                captured=datetime.fromtimestamp(image.stat().st_mtime, timezone.utc).isoformat(),
                width=width, height=height, rawSha256=sha(image), layoutSha256=sha(layout),
                captureEnvironment='HarmonyOS native emulator 127.0.0.1:5555', uiVersion='light UI 2026-10-23')


def entries():
    capture_specs = [
        ('home', 'hm-home', [(1, '巡检底部导航', lambda ns: button_for(ns, '巡检')),
                             (2, 'AI助手入口', lambda ns: button_for(ns, 'AI 助手')),
                             (3, '专家咨询入口', lambda ns: button_for(ns, '专家咨询'))]),
        ('photo', 'hm-photo', [(1, '照片上传区域', lambda ns: min(
            (n for n in ns if n['type'] == 'Stack' and n.get('clickable') == 'true' and visible(n)),
            key=lambda n: (bounds(n)[2] - bounds(n)[0]) * (bounds(n)[3] - bounds(n)[1]))),
                              (2, '选图后启用开始分析', lambda ns: button_for(ns, '开始 AI 分析'))]),
        ('records', 'hm-records', [(1, '清空图标 无记录时禁用', lambda ns: next(
            n for n in ns if n['type'] == 'Button' and bounds(n)[0] > 1000 and bounds(n)[1] < 500)),
                                  (2, '去上传照片', lambda ns: button_for(ns, '去上传照片'))]),
        ('devices', 'hm-admin', [(1, '刷新设备示例', lambda ns: next(
            n for n in ns if n['type'] == 'Button' and bounds(n)[0] > 1000 and bounds(n)[1] < 500)),
                               (2, '开启风扇 本地演示入口', lambda ns: button_for(ns, '开启风扇'))]),
        ('settings-connected', 'hm-settings', [(1, '平台服务地址输入框', lambda ns: next(
            n for n in ns if n['type'] == 'TextInput' and n.get('text', '').startswith('http'))),
                                             (2, '保存并测试连接', lambda ns: button_for(ns, '保存并测试连接'))]),
        ('assistant', 'hm-assistant', [(1, '问题输入框', lambda ns: next(n for n in ns if n['type'] == 'TextArea')),
                                       (2, '发送箭头 空问题时禁用', lambda ns: next(
                                           n for n in ns if n['type'] == 'Button' and bounds(n)[0] > 1000 and bounds(n)[1] > 2200)),
                                       (3, '转专家咨询', lambda ns: button_for(ns, '转专家咨询 ↗'))]),
        ('consultation', 'hm-consultation-top', [(1, '咨询方向', lambda ns: button_for(ns, '牛病与健康')),
                                               (2, '问题标题输入框', lambda ns: next(n for n in ns if n.get('hint') == '例如：牛只连续两天行走跛行')),
                                               (3, '我的咨询', lambda ns: button_for(ns, '我的咨询'))]),
        ('consultation-form', 'hm-consultation-submit', [(1, '问题详情输入框', lambda ns: next(n for n in ns if n['type'] == 'TextArea')),
                                                        (2, '提交咨询', lambda ns: button_for(ns, '提交咨询'))]),
        ('consultation-records', 'hm-consultation-records', [(1, '我的咨询列表', lambda ns: button_for(ns, '我的咨询')),
                                                          (2, '刷新咨询', lambda ns: button_for(ns, '刷新')),
                                                          (3, '查看已有测试咨询', lambda ns: clickable_for(ns, next(n['text'] for n in ns if n.get('text', '').startswith('UI_TEST_NATIVE') and visible(n))))]),
        ('consultation-detail', 'hm-consultation-detail', [(1, '返回咨询列表', lambda ns: button_for(ns, '返回咨询列表')),
                                                        (2, '核对已撤回状态', lambda ns: next(n for n in ns if n.get('text', '').startswith('已撤回 ·') and visible(n)))]),
        ('news', 'hm-news-list', [(1, '今日小知识', lambda ns: clickable_for(ns, '今日小知识')),
                                (2, '订阅设置', lambda ns: button_for(ns, '订阅设置')),
                                (3, '切换小知识', lambda ns: button_for(ns, '小知识'))]),
        ('article', 'hm-knowledge-detail', [(1, '收藏或取消收藏', lambda ns: button_for(ns, '已收藏' if any(n.get('text') == '已收藏' for n in ns) else '收藏')),
                                           (2, '延伸阅读', lambda ns: button_for(ns, '延伸阅读')),
                                           (3, '问AI助手', lambda ns: button_for(ns, '问 AI 助手'))]),
        ('favorites', 'hm-news-favorites', [(1, '收藏栏目', lambda ns: button_for(ns, '收藏'))]),
        ('messages', 'hm-news-messages', [(1, '消息栏目', lambda ns: next(n for n in ns if n['type'] == 'Button' and n.get('text', '').startswith('消息 '))),
                                         (2, '全部已读', lambda ns: button_for(ns, '全部已读'))]),
        ('subscriptions', 'hm-subscriptions', [(1, '新闻提醒开关', lambda ns: [n for n in ns if n['type'] == 'Toggle'][0]),
                                             (2, '每日知识开关', lambda ns: [n for n in ns if n['type'] == 'Toggle'][1]),
                                             (3, '健康防疫关注方向', lambda ns: next(n for n in ns if n['type'] == 'Checkbox' and n.get('text') == 'health'))]),
    ]
    return {key: load_capture(raw, key, specs) for raw, key, specs in capture_specs}


def current_flows():
    flows = mobile_flows('hm')
    for flow in flows:
        for field in ('purpose', 'result', 'exception'):
            flow[field] = flow[field].replace('AI识牛', '巡检')
        flow['steps'] = [text.replace('AI识牛', '巡检') for text in flow['steps']]
        flow['nodes'] = [text.replace('AI识牛', '拍照巡检') for text in flow['nodes']]
    flows[0]['purpose'] = '启动后进入白底总览，底部图标导航为总览、巡检、记录和管理。首页提供AI助手、专家咨询、养牛资讯以及右上角服务设置入口。'
    flows[0]['steps'][0] = '点击红框1的“巡检”图标进入“拍照巡检”；点击“记录”或“管理”切换主视图。'
    flows[0]['steps'][1] = '点击红框2“AI助手”或红框3“专家咨询”进入独立页面，左上角箭头返回上一级。'
    flows[0]['steps'][2] = '总览明确标识养殖场与设备为示例数据；页签切换后显示内容顶部。'
    flows[0]['exception'] = '主页面未出现时检查应用安装、HarmonyOS SDK版本或模拟器运行状态；当前没有账号密码登录页。'
    flows[1]['steps'][1] = '红框2“开始AI分析”在未选图时禁用；选图成功后点击，等待进度结束。分析过程中按钮禁用，避免重复提交。'
    flows[2]['steps'][1] = '记录页右上角垃圾桶图标为清空入口；有记录时可点击并确认，当前空列表截图中该图标禁用。'
    flows[2]['steps'][2] = '进入“管理”，红框1刷新示例数据；红框2为风扇演示入口，点击仅新增本地操作记录并提示本地演示。'
    flows[4]['steps'][0] = '在红框1输入区填写现场问题，点击红框2的向上箭头发送；输入为空时发送按钮禁用。'
    flows[4]['steps'][2] = '红框3“转专家咨询”将对应问题带入表单；复制图标用于复制回答，参考链接可点击复制地址。失败时点击重试。'
    flows[6]['screenshots'] = [('hm-consultation-records', '咨询列表与刷新入口'),
                               ('hm-consultation-detail', '已撤回的真实联调样例')]
    flows[6]['steps'][0] = '在列表图红框1切换“我的咨询”，红框2刷新，点击红框3的咨询标题进入详情。'
    flows[6]['steps'][1] = '详情图红框2展示现有测试记录的已撤回状态；UI_TEST条目为联调演示，不是真实病例。红框1返回列表。'
    flows[7]['steps'][2] = '详情图红框2“延伸阅读”复制来源地址，红框3可带入AI助手；行业新闻显示“原文链接”，知识卡显示“延伸阅读”。'
    flows[8]['steps'][0] = '在第8章图8-2红框1点击星形收藏入口，选中后显示“已收藏”；到本章收藏栏目红框1查看，最多保留100条。'
    flows[9]['result'] = '应用前台同步站内消息；当前未配置鸿蒙Push Kit，关闭应用进程后不会继续发送系统锁屏通知。'
    flows[9]['exception'] = '联网后刷新确认更新时间；系统远程推送需要另外配置平台证书、推送服务与用户授权。'
    return flows


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    STAGE.mkdir(parents=True, exist_ok=True)
    backup = WORK / '更新前材料备份'
    if not backup.exists():
        shutil.copytree(TARGET, backup, ignore=shutil.ignore_patterns('~$*', '申请表模板-待本人填写.docx'))
    app = deepcopy(next(app for app in APPS if app['key'] == 'hm'))
    app['summary'] = '鸿蒙原生移动巡检客户端，采用新版白底界面与底部图标导航，包含照片本地演示、记录、设备演示、DeepSeek问答、专家咨询单、新闻与每日小知识。'
    app['navigation'] = '总览、巡检、记录、管理；总览和管理进入AI助手、专家咨询与养牛资讯，齿轮图标进入服务设置。'
    app['status'] = '照片分析与设备控制为本地演示；AI助手、咨询单提交查询撤回、养牛资讯通过平台接口运行。当前未配置真人专家回复和锁屏推送。'
    app['preflight'] = '确认应用可在HarmonyOS真机或模拟器启动；使用问答、咨询和资讯时，先确认平台服务地址与网络可达。'
    app['screenshot_origin'] = '本手册采用HarmonyOS原生模拟器中的实际APP页面，只添加红框编号并按操作区域裁剪，不修改页面业务数据。原始完整截图与界面节点坐标一并保留。'
    app['faq'] = [
        ('页面无数据或数据不更新', '总览和设备页的固定值为明确标识的示例数据。问答、咨询和资讯需要连接平台；连接失败时先核对服务地址、网络和访问凭证，再查看缓存提示与数据日期。'),
        ('照片分析能否确认疾病', '当前照片分析采用本地演示逻辑，生成的编号、分值和建议不是真实模型推断。疾病需要由兽医结合现场检查与必要检测确认。'),
        ('AI助手连接失败或切换知识库', '进入服务设置测试平台连接。供应商密钥由后端管理，回答标识区分DeepSeek与知识库。平台访问凭证和DeepSeek密钥属于不同配置项。'),
        ('咨询提交失败或没有专家回复', '检查标题与详情字数、网络和访问身份；失败时保留草稿。当前保存咨询单并支持查询、撤回，尚未配置真人专家接单、排班与回复。'),
        ('资讯更新失败或新闻较旧', '查看来源同步状态和最后更新时间。平台保存原发布日期，断网时可阅读已有缓存和收藏，恢复连接后再刷新。'),
        ('为什么关闭应用后收不到资讯通知', '当前提供应用内推荐、消息与未读提醒，尚未配置鸿蒙Push Kit远程推送。应用进程关闭后不会发送系统锁屏通知。'),
    ]
    app['technical'] = 'ArkUI声明式界面、共享AppTheme配色、@State与@Prop状态更新、图标导航、系统选图器、Preferences本机持久化、平台HTTP接口、页签滚动位置重置。'
    app['workflows'] = current_flows()
    screenshots = entries()
    pages = base.prepare_source(app, STAGE)
    code = base.source_document(app, STAGE, pages)
    manual = walkthrough.manual(app, STAGE, screenshots)
    base.auxiliary(app, STAGE)
    used_keys = [key for flow in app['workflows'] for key, _ in flow['screenshots']]
    final_manifest = []
    for key in used_keys:
        entry = deepcopy(screenshots[key])
        raw = Path(entry['file'])
        raw_dest = STAGE / '配图' / '原始截图' / raw.name
        layout_dest = STAGE / '配图' / '界面节点' / Path(entry['layout']).name
        layout_dest.parent.mkdir(exist_ok=True)
        shutil.copy2(entry['layout'], layout_dest)
        annotated = STAGE / '配图' / f'{key}-红框.png'
        entry['file'] = str(TARGET / raw_dest.relative_to(STAGE))
        entry['layout'] = str(TARGET / layout_dest.relative_to(STAGE))
        entry['annotated'] = str(TARGET / annotated.relative_to(STAGE))
        entry['annotatedSha256'] = sha(annotated)
        final_manifest.append(entry)
    (STAGE / '截图来源与标注清单.json').write_text(json.dumps(final_manifest, ensure_ascii=False, indent=2), 'utf-8')
    report = dict(name=NAME, key='hm', stats=app['stats'], code=str(TARGET / code.name),
                  manual=str(TARGET / manual.name), screenshotCount=len(used_keys), workflowFigures=10,
                  uiVersion='新版白底UI 2026-10-23', sourceRoot=str(ROOT / 'hm/entry/src/main/ets'))
    (STAGE / '新版材料清单.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    (STAGE / '本次更新说明.txt').write_text(
        '本次按新版鸿蒙APP源程序与实际界面更新，软件名称及版本仍为数牧增效牛舍智能巡检与预警平台 V1.0。\n'
        f"源程序为全部{app['stats']['fileCount']}个ArkTS文件，共{app['stats']['physicalLines']}行物理代码、{app['stats']['nonemptyLines']}行非空代码。\n"
        f"代码材料{app['stats']['codePages']}页，每页50行，最后一页{app['stats']['nonemptyLines'] % 50 or 50}行；没有补写代码凑页数。\n"
        f'手册沿用原模板，10张流程图，{len(used_keys)}张新版真实运行截图，红框编号对应实际控件。\n'
        '申请表由申请人最后填写。本次更新不改变实际开发完成日期、发表情况或权属信息。\n', 'utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
