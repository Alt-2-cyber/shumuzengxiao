# 移动端 AI 助手与专家咨询

更新日期：2026-10-22。适用于 hm 鸿蒙客户端与 wx 微信小程序。

## 页面入口

总览和管理页均有“AI 助手”“专家咨询”入口，保留原来的四个底部栏目。

- AI 助手：快捷问题、多轮问答、最近 40 条本机会话、复制回答与参考链接、失败重试、转专家咨询、清空会话。
- 专家咨询：牛病与健康、饲养与营养、设备与环境、其他问题四个方向；紧急程度、耳标、问题标题、详情、回访方式；本机草稿、提交回执、咨询列表、详情与撤回。
- 服务设置：平台地址、可选的平台访问凭证、保存并检查连接。

## 后端与 DeepSeek

接口统一位于 `/api/mobile-support`：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /catalog | 助手模式与咨询方向 |
| GET | /session | 小程序首次生成随机咨询身份 |
| POST | /assistant | 问题与最多 8 条上下文 |
| GET | /consultations | 当前客户端最近 50 条咨询 |
| POST | /consultations | 幂等提交咨询 |
| POST | /consultations/{id}/cancel | 撤回自己的咨询 |

DeepSeek 兼容接口配置通过服务端环境变量读取：

```text
CATTLE_ASSISTANT_ENDPOINT=https://api.deepseek.com/chat/completions
CATTLE_ASSISTANT_MODEL=deepseek-chat
CATTLE_ASSISTANT_API_KEY=<由服务端保管的密钥>
```

本机密钥通过 Windows DPAPI 加密存放于 `.run/cattle-assistant-key.clixml`。
`scripts/start-all.ps1` 启动后端时自动读取；只适用于保存该凭证的 Windows 用户。
该文件不属于源码，不能复制到客户端或软著材料中。客户端的“平台访问凭证”也不是 DeepSeek 密钥。

未配置供应商时使用本地养殖巡检知识库。供应商超时或响应无效时，返回知识库答案并明确提示切换原因。
问答接口不读取实时设备数据，不把模拟照片分析当作已验证的牛只病历。

## 咨询持久化与范围

咨询保存到 MySQL 的 `mobile_consultation` 表，建表脚本位于后端 `schema-mysql.sql`。
客户端随机身份只在本机保存；数据库存储其 SHA-256 摘要。查询和撤回必须提供相同的 `X-Mobile-Token`。
重复提交相同编号与相同内容返回原咨询单，编号冲突会拒绝，不重复新增记录。
启用 API 访问控制后，移动接口允许 viewer/operator/clinical/admin，采集角色无权访问。

目前咨询状态为“待受理”或“已撤回”。尚未接入真实专家账号、排班、通知和人工回复后台；保存咨询单不代表已联系某位兽医。
两端现有的照片分析和旧设备示例数据沿用原有实现，不因新增助手而变成实时诊断结果。

## 本地运行

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1 -Service all -Profile mysql
```

小程序开发工具默认平台地址为 `http://127.0.0.1:8080`；本机私有配置关闭合法域名检查，仅供开发工具联调。
鸿蒙模拟器默认使用 `http://10.0.2.2:8080`。
真机通过页面的服务设置填写可访问的地址；小程序正式运行需配置 HTTPS 合法域名。

本机会话最多保存 40 条，咨询列表最多显示最近 50 条。清除应用数据或更换客户端后，当前匿名咨询身份不会自动同步；后续若增加账号体系，应将匿名身份迁移至账号，而不是向所有人公开咨询记录。

## 验证入口

- 后端测试：`mvn test -Dtest=MobileSupportTest,ApiKeyAccessPolicyTest`。
- 小程序静态检查：在 wx 目录运行 `node_modules/.bin/tsc --noEmit`。
- 鸿蒙：DevEco 的 `assembleHap`，并在模拟器中检查提问、咨询提交、详情和撤回后的状态刷新。
- 本次联调截图与脚本位于 `.run/cattle-preview`，标记为 UI_TEST / 联调测试的咨询不是真实病例。

本次增加了实际源码。已有软著导出的代码页和手册是旧快照，提交申请前应按最终确认版本重新导出。
