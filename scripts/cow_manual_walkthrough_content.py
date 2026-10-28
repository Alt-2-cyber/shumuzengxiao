"""Operation chapters tied to actual screenshots from each client."""

from copy import deepcopy
from cow_copyright_content import WEB_FLOWS


def mobile_flows(key):
    prefix = "鸿蒙" if key == "hm" else "小程序"
    source = "pages/Index.ets" if key == "hm" else "pages/index、pages/diagnosis、pages/records、pages/admin"
    assistant_images = [("hm-assistant", "问答结果和输入区")] if key == "hm" else [
        ("wx-assistant-input", "输入问题并发送"), ("wx-assistant-answer", "接收回答并转咨询")]
    settings_images = [(f"{key}-settings", "平台服务地址和连接测试")]
    consultation_images = [(f"{key}-consultation-top", "咨询方向和问题标题"), (f"{key}-consultation-submit", "填写详情后提交")]
    record_images = [("hm-consultation-records", "本机身份下的咨询记录")] if key == "hm" else [("wx-consultation-receipt", "平台保存的演示咨询回执")]

    def flow(title, nodes, purpose, steps, result, exception, images, code):
        return dict(title=title, nodes=nodes, purpose=purpose, steps=steps, result=result,
                    exception=exception, screenshots=images, source=code)

    return [
        flow("打开首页与页面导航", ["启动客户端", "进入总览", "选择功能入口", "返回总览"],
             f"启动{prefix}客户端后，首先进入总览。底部为总览、AI识牛、记录和管理，首页同时提供AI助手、专家咨询、养牛资讯入口。",
             ["点击底部“AI识牛”进入图片页面；点击“记录”或“管理”切换主视图。",
              "点击首页“AI助手”或“专家咨询”进入独立页面，使用左上角返回按钮返回。",
              "查看总览时，区分本地记录统计与内置的牛只、设备示例值。"],
             "当前页面随所选入口切换；总览中的固定设备数值不代表硬件当前在线。",
             "主页面未出现时检查安装、微信基础库或客户端运行环境；当前没有账号密码登录页。",
             [(f"{key}-home", "总览中的实际功能入口")], source),
        flow("照片选择与本地分析演示", ["打开AI识牛", "选择单张图片", "开始演示分析", "查看本地记录"],
             "照片页验证选图、预览、分析进度和保存流程。当前照片结果由本地模拟函数生成，不能用于疾病确诊。",
             ["在红框1的上传区域选择一张图片；取消选择时不生成结果。",
              "选图后点击红框2“开始AI分析”，等待进度结束；未选图片会提示补充图片。",
              "结果生成后可切换“记录”查看；结果、分值、牛只编号均按演示数据解释。"],
             "完成分析会新增本地记录。截图保留未选图状态，展示操作起点，未伪造识别结果。",
             "图片权限、原图失效或存储不足时重新选择；当前不向真实视觉识别服务上传图片。",
             [(f"{key}-photo", "上传区域和开始分析按钮")], source),
        flow("记录浏览与管理页面", ["打开记录", "查看历史或空状态", "进入管理", "查看设备示例"],
             "照片记录保存在当前客户端本机，管理页提供示例设备与快捷操作。请将其与后端问答、资讯的真实网络连接分开理解。",
             ["进入“记录”，查看时间、图片与结果；暂无记录时保留空状态。",
              "“清空”需确认后删除当前本地记录，取消确认会保留原数据。",
              "进入“管理”查看设备示例；点击刷新只重读页面数据，控制提示不等于硬件执行回执。"],
             "本机照片记录与管理视图可浏览；截图中的空记录和示例设备均为实际页面状态。",
             "卸载或清理本机数据可能丢失记录；没有回收站，设备实态需到Web与现场核对。",
             [(f"{key}-records", "记录空状态和清空入口"), (f"{key}-admin", "管理页实际入口")], source),
        flow("设置平台地址并测试连接", ["打开服务设置", "填写平台地址", "保存并测试", "查看连接结果"],
             "服务设置供AI助手、专家咨询和资讯访问同一平台。平台访问凭证与DeepSeek供应商密钥不是同一个配置项。",
             ["在助手、咨询或资讯页右上角点击设置图标，进入服务设置。",
              "填写平台服务地址；开启平台访问控制时填写对应访问凭证。",
              "点击“保存并测试连接”，根据页面反馈确认可达或修改错误地址。"],
             "服务设置写入本机，测试成功显示连接正常；DeepSeek密钥只在服务端保存。",
             ("模拟器使用10.0.2.2访问电脑后端；真机应填写可访问的部署地址。" if key == "hm" else
              "开发工具可访问电脑本机；小程序真机需要HTTPS合法域名，不能把手机localhost当作电脑。"),
             settings_images, "pages/SupportSettings、support/SupportService" if key == "hm" else "pages/support-settings、utils/support.ts"),
        flow("AI助手问答与转专家咨询", ["描述巡检问题", "点击发送", "接收来源标识", "继续提问或转咨询"],
             "助手用于养殖管理问答。当前服务端配置DeepSeek，服务不可用时会明确切换知识库，不读取未提供的实时设备数据。",
             ["在输入区填写耳标、异常时间和现场观察，点击发送按钮。",
              "等待回答后阅读模型或知识库标识；可继续提问，或复制回答与参考链接。",
              "点击“转专家咨询”，将问题带入咨询表单；接口失败时使用“重试”，不会伪装成成功。"],
             "回答与会话保存在本机；健康建议仅用于巡检辅助，需要兽医结合实际检查判断。",
             "检查平台服务、网络和访问凭证；供应商异常时页面可能显示知识库模式及切换提示。",
             assistant_images, "pages/Assistant、support/SupportService" if key == "hm" else "pages/assistant、utils/support.ts"),
        flow("填写并提交专家咨询", ["选择咨询方向", "填写标题详情", "设置优先级", "提交平台"],
             "咨询支持牛病与健康、饲养与营养、设备与环境及其他方向。提交前可保留本机草稿。",
             ["点击咨询方向与紧急程度；按需填写耳标或栏位。",
              "填写5至80字标题、10至2000字详情，补充异常时间、采食和测量方法，联系方式可选填。",
              "在表单底部点击“提交咨询”；服务返回回执后进入我的咨询。"],
             "咨询单保存在平台数据库，状态为待受理；尚未接入真人专家排班和回复服务。",
             "校验或网络失败会保留草稿，可用原编号重试；呼吸困难等紧急情况应直接联系当地兽医。",
             consultation_images, "pages/Consultation、support/SupportService" if key == "hm" else "pages/consultation、utils/support.ts"),
        flow("查看咨询回执和撤回状态", ["打开我的咨询", "选择咨询记录", "查看平台状态", "确认撤回"],
             "我的咨询按当前客户端身份查询最近记录。待受理只表示平台保存了咨询，不代表已联系或分配某位专家。",
             ["点击“我的咨询”，必要时刷新列表，再点击对应标题进入详情。",
              "核对问题、提交时间和状态；操作手册样例或UI_TEST条目均为联调演示。",
              "待受理详情可点“撤回咨询”，确认后状态改为已撤回，历史记录仍保留。"],
             "平台保存咨询及撤回状态；清理客户端身份后不能自动恢复同一匿名咨询列表。",
             "读取失败时有缓存会提示其状态尚未刷新；请勿据缓存认定专家已接单或已回复。",
             record_images, "pages/Consultation、support/ConsultationDetail" if key == "hm" else "pages/consultation"),
        flow("阅读新闻与每日小知识", ["打开养牛资讯", "选择新闻或知识", "阅读详情", "查看原文来源"],
             "资讯页面读取平台采集的官方新闻和项目整理的知识卡。新闻标注原发布机构、日期与原文地址。",
             ["从首页或管理页进入“养牛资讯”；点击今日小知识阅读当天推荐。",
              "选择“新闻”或“小知识”，可按健康、营养等分类或搜索标题和摘要。",
              "打开详情后查看来源；点击原文或延伸阅读链接会复制地址，可在浏览器查看完整来源。"],
             "新闻详情为索引与阅读提示；知识卡为项目整理内容。详情可进一步进入AI助手或专家咨询。",
             "来源暂不可用会显示其同步状态并保留历史内容；不要把采集时间冒充发布时间。",
             [(f"{key}-news-list", "新闻和今日知识入口"), (f"{key}-knowledge-detail", "知识卡详情与阅读操作")],
             "pages/News、pages/NewsDetail、news/NewsService" if key == "hm" else "pages/news、pages/news-detail、utils/news.ts"),
        flow("收藏内容与管理未读消息", ["打开详情", "收藏或取消收藏", "查看消息", "标记已读"],
             "收藏和已读状态保存在本机，收藏保留内容快照；消息栏目用于查看应用内推荐和更新提醒。",
             ["在内容详情点击收藏，再到“收藏”栏目查看；再次点击可取消，最多保留100条。",
              "点击“消息”查看推荐，打开对应内容后该条消息会变为已读。",
              "点击“全部已读”清除当前未读提醒；同一天刷新不会重复产生每日知识消息。"],
             "收藏不会上传到其他客户端，已读状态会在本机重启后保留。",
             "清理应用数据可能丢失收藏与偏好；无网络时先阅读缓存，再在联网后刷新。",
             [(f"{key}-news-favorites", "本机收藏"), (f"{key}-news-messages", "消息与全部已读")],
             "news/NewsService" if key == "hm" else "utils/news-state.ts、utils/news.ts、pages/news"),
        flow("配置订阅与处理更新失败", ["进入订阅设置", "切换提醒开关", "勾选关注方向", "返回并同步"],
             "新闻提醒和每日知识可分别开启，分类偏好影响后续新发现的新闻提醒。当前是应用内推送，没有启用锁屏远程通知。",
             ["点击右上角“订阅设置”，按需要切换新闻更新和每日小知识开关。",
              "勾选关注方向后返回资讯；设置会保存在当前设备，关闭提醒不删除已有消息。",
              "打开资讯时自动同步，也可点击刷新。网络失败时读取上次缓存并显示失败提示。"],
             "应用前台同步站内消息；关闭应用进程后不会继续发送系统通知或微信订阅消息。",
             "联网后刷新确认更新时间；真机推送需要额外平台证书、模板与用户授权。",
             [(f"{key}-subscriptions", "提醒开关和关注方向")],
             "pages/News、news/NewsService" if key == "hm" else "pages/news、utils/news-state.ts"),
    ]


def web_flows():
    flows = deepcopy(WEB_FLOWS)
    keys = ["web-home", "web-environment", "web-behavior", "web-audio", "web-vision", "web-health", "web-devices", "web-models", "web-realtime", "web-evidence"]
    for item, key in zip(flows, keys):
        item["screenshots"] = [(key, "当前运行界面及操作入口")]
    return flows
