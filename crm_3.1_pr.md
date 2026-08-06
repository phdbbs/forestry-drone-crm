# 林业无人机业务 CRM 系统 V3.1 — 产品需求文档（Codex 开发版）

> **版本**：V3.1（基于 V1.2 → V2.0 → V3.0 迭代 + 联系人动态采集等新需求）
> **日期**：2026-08-06
> **定位**：单人使用的轻量级私有 CRM 系统，服务于林业无人机业务的线索获取、商机跟进、客户与联系人管理
> **技术栈**：Python Flask + SQLite + 原生 HTML/JS（SPA 模式）+ 本地 AI（OpenAI 兼容协议）

---

## 一、系统概述

### 1.1 项目背景
面向林业无人机行业（病虫害监测、林区巡检、航拍核查等业务），构建一套个人使用的 CRM 系统，实现从招标线索自动采集、AI 结构化抽取、商机转化、客户/联系人管理、日常联络与联络计划跟踪、新闻动态采集的全流程管理。

### 1.2 核心约束
| 约束项 | 说明 |
|--------|------|
| 部署方式 | 私有服务器本地运行（本机 127.0.0.1:5001） |
| 数据库 | SQLite（单文件，自动迁移新增列/表） |
| 用户 | 单用户，无需权限管理；采集信息仅内部可见 |
| 后端 | Python Flask（轻量化） |
| 前端 | SPA 模式，原生 HTML/CSS/JS（内联单文件） |
| AI 集成 | OpenAI 兼容协议，支持自定义 Endpoint/Key/模型（默认本机 qwen3-14b-mlx） |
| 爬虫 | 多来源配置（中国政府采购网中央/地方公告等），增量采集（记录上次采集时间点） |

---

## 二、功能模块总览

| 模块 | 说明 |
|------|------|
| 智能工作台 | 统计卡、紧急线索、今日联络、AI 紧急任务（每日跟进方案，30 分钟缓存+手动刷新） |
| 线索管理 | 待转化/已转化/已删除三 tab；搜索（名称/地区/创建时间）；采集/手工来源标识；转化自动创建客户与联系人 |
| 商机管理 | 列表/看板视图；编辑；来源 URL（转化带招标原文）；详情弹窗含流转时间轴（日常联络记录）与"添加联络记录" |
| 联系人管理 | 表格化；搜索（姓名/职位/客户/角色）；排序；查看/编辑/删除；详情含"动态信息"板块 |
| 客户管理 | 表格化；搜索（名称/类型/等级/地区）；详情四 tab：联系人/商机/联络记录/动态信息 |
| 日常联络 | 表格化列表；搜索（日期/客户/商机/内容）+列头排序；详情/编辑；可关联商机（非必选） |
| 联络计划 | 独立模块；组合搜索；新增计划（客户/联系人联动、可关联商机）；详情含历史联系记录；"联络"执行后自动生成日常联络记录 |
| 看板管理 | 多列拖拽卡片，截止日期，来源关联 |
| 数据报表 | 线索/商机/金额/转化率统计 + 月度趋势/漏斗/赢丢单图表 |
| 系统设置 | AI 配置、采集来源与增量时间点、新闻/动态采集配置、采集日志、技能管理 |

---

## 三、核心功能详述

### 3.1 线索管理

**AI 真实采集**
- 多来源 URL 配置（默认中国政府采购网-中央公告、地方公告），来源可增删启停
- 抓取列表页 → 时间过滤 → 详情页 → AI 结构化抽取（标题/客户方/联系人/电话/地址/预算/截止/摘要），规则兜底提取"项目联系人/项目联系电话"
- 增量采集：每次采集记录"上次采集时间点"，下次只抓取该时间点之后发布的信息，避免重复与漏查；首次自动回溯最近 7 天；来源 URL 去重
- 后台线程执行 + 状态轮询（页面显示进度），AI 调用串行化+失败自动重试

**状态与操作**
- 待转化：查看/转化/删除（软删除）
- 已转化：不可修改（后端 400 拦截），仅查看
- 已删除：可编辑、恢复为待转化、再转化
- 转化弹窗：自动预填采集到的客户/联系人/电话；未选择客户/联系人时自动创建（客户=采购方，联系人=项目联系人），商机自动带来源 URL

**搜索**：名称、地区、创建时间范围，点击"搜索"按钮执行（全局按钮式搜索）。

### 3.2 商机管理
- 行内编辑：标题/客户/联系人/金额/阶段/赢率/预计关闭/来源 URL
- 来源：转化自动带招标原文 URL（详情可点击跳转）；手工添加可填写
- 详情弹窗：基本信息 + 来源链接 + 流转时间轴（该商机的日常联络记录：时间/方式/内容/联系人/预计下次）+ "添加联络记录"按钮 + 编辑
- 列表/看板切换；管道图按配置阶段统计；搜索（名称/客户/阶段）+ 列头排序

### 3.3 客户管理
- 表格：名称/类型/等级/地区/联系人/来源，列头排序；搜索（名称/类型/等级/地区，按钮式）
- 客户详情四 tab：
  - 联系人：该客户联系人列表
  - 商机：该客户名下商机（金额/阶段/赢率），点击名称跳转商机管理并打开详情
  - 联络记录：该客户联系记录（联系人/时间/内容/预计联系），可"新增日常联络"（自动带客户）
  - 动态信息：采集的新闻列表（采集时间/来源/标题/摘要/事件时间），支持"采集新闻"与删除
- 客户资料含"官网"字段（新闻采集来源）

### 3.4 联系人管理
- 表格：姓名/职位/所属客户/电话/微信/角色/重要性；搜索（姓名/职位/客户/角色）+ 列头排序
- 详情弹窗：基本信息 + **动态信息板块**

### 3.5 日常联络
- 表格：时间/客户/商机/联系人/内容/预计联系；列头排序
- 搜索：日期范围/客户/商机/内容（按钮式）
- 详情弹窗、编辑；记录可关联商机（非必选）
- 日期控件统一为年月日

### 3.6 联络计划（独立模块）
- 独立导航页；搜索（内容/客户/联系人/状态/计划日期范围）+ 新增联系计划按钮 + 可排序列表
- 计划字段：计划日期、客户、联系人（客户联动）、关联商机（可选）、计划联系内容
- **详情**：本次计划联系内容 + 实际联系内容（若有）+ 该客户/联系人之前的联系记录时间轴
- **联络（执行）**：查看计划内容 → 填写本次联系内容/联系方式/下次联系时间/预计联系内容 → 提交后计划标记已完成，**本次联系内容自动生成到日常联络记录**（互通）

### 3.7 AI 每日跟进分析
- 基于联系记录/待办跟进/活跃线索/商机/久未联系联系人数据，调用本地 AI 生成当日跟进方案（3-8 条任务）
- 展示在工作台"AI 紧急任务"卡片，30 分钟缓存 + 手动刷新

### 3.8 新闻/动态信息采集
**联系人动态信息**
- 来源：客户官网 + 配置的媒体/官网来源（含中国政府采购网公告）
- 新闻内容出现联系人姓名时自动关联，生成联系人动态（会议/调研/讲话/任命/获奖等公开活动提及）
- 联系人详情"动态信息"板块：采集时间、来源、新闻标题（链接直达原文）、涉及摘要、事件时间，按时间倒序

**客户新闻**
- 按客户名称/简称匹配官网与媒体新闻，入库客户动态（详情"动态信息"tab）
- 同一新闻既涉及客户又涉及联系人时，同时关联客户与联系人

**采集日志**
- 每次采集任务记录：执行时间、来源、采集条数、成功/部分异常/失败状态
- 设置页可查看最近 50 条日志

### 3.9 系统设置
- AI 配置：Endpoint/API Key/模型，测试连接（超时 180s）
- 采集配置：来源 URL（多行"名称|URL"）、上次采集时间点、每次 AI 抽取上限、关键词过滤开关
- 新闻/动态采集：来源配置、批量采集（客户新闻+联系人动态）、采集日志
- 技能管理：内置技能展示（"内置"徽标）、自定义技能删除

---

## 四、数据模型

| 表 | 关键字段 |
|----|----------|
| customers | name/short_name/customer_type/level/region/website/source/remark/is_archived |
| contacts | name/title/phone/email/wechat/role/tags/importance/customer_id/notes |
| leads | title/bid_number/budget/deadline/region/purchaser/contact_name/contact_phone/address/source_url/source_platform/match_*/status/customer_id |
| opportunities | title/amount/source_url/current_stage/probability/expected_close/customer_id/contact_id/lead_id |
| activities | customer_id/contact_id/opportunity_id/lead_id/method/content/activity_time/next_followup_* |
| followups | customer_id/contact_id/opportunity_id/lead_id/plan_date/content/actual_*/source_activity_id |
| customer_news | customer_id/title/content/url/source_name/change_type/publish_date/event_time |
| contact_news | contact_id/customer_id/title/content/url/source_name/summary/publish_date/event_time |
| crawl_logs | task_type/sources/status/items_count/error_count/message/started_at/finished_at |
| kanban_boards/columns/cards | 看板及卡片，卡片带截止日与来源 |
| system_config | key/value/description（AI 配置、采集来源、新闻来源、检查点、AI 任务缓存等） |
| skills | 技能管理 |

---

## 五、主要 API

**线索**：GET/POST /api/leads（支持 search/status/level/region/date_from/date_to）；GET/PUT/DELETE /api/leads/<id>（已转化禁止修改）；POST /convert（自动建客户/联系人）；POST /abandon；POST /claim /release

**商机**：GET/POST /api/opportunities；GET/PUT/DELETE /api/opportunities/<id>；POST /<id>/stages；GET /api/stages

**客户/联系人**：标准 CRUD；GET /customers/<id> 含 contacts/opportunities/news；GET /contacts/<id> 含 contact_news

**日常联络**：GET/POST /api/activities（支持 customer_id/opportunity_id/date_from/date_to 过滤）；GET/PUT/DELETE /<id>

**联络计划**：GET/POST /api/followups（支持过滤）；GET /<id>（含历史联系记录）；POST /<id>/execute（执行并生成日常联络）；PUT/DELETE

**采集**：POST /api/crawl（后台启动）+ GET /api/crawl/status；POST /api/customers/<id>/collect-news；POST /api/contacts/<id>/collect-news；POST /api/news/collect-all；GET /api/news/logs；DELETE /api/news/customer/<id>、/api/news/contact/<id>

**AI**：GET /api/ai/urgent-tasks（缓存）+ POST /refresh；POST /api/config/test-ai

**其他**：/api/dashboard、/api/suggestions、/api/analytics、/api/kanban/*、/api/config、/api/skills、/api/options

---

## 六、页面统一规范

- 业务页面（线索/商机/联系人/客户/日常联络/联络计划）统一：**上部搜索区 + 下部表格 + 列头点击排序 + 操作列（查看/编辑/删除 等）**
- 全局搜索框：输入完成后点击"搜索"按钮执行，配"重置"
- 日期控件统一到年月日

---

## 七、测试与验收标准

**自动化测试**
- AICS 集成套件 68 条：全模块 happy path
- 边界用例 26 条：输入校验/状态限制/看板联动/跟进同步/数据分析正确性
- 页面级回归（Playwright 真实浏览器）：三 tab 流转、搜索按钮、转化自动建客户联系人、商机编辑/时间轴、客户四 tab、日常联络列表/排序、联络计划全流程、新闻采集展示

**验收清单**
- [x] 线索采集：真实招标信息 AI 抽取（标题/客户/联系人/电话/地址/预算/来源URL），增量不重复
- [x] 转化：自动创建客户与联系人，商机带来源链接
- [x] 已转化不可修改；已删除可恢复再转化
- [x] 商机编辑/来源/流转时间轴/添加联络记录
- [x] 客户详情四 tab，商机跳转
- [x] 联系人动态信息采集与展示（新闻出现姓名自动关联）
- [x] 客户新闻采集与联系人同步关联，同新闻双关联
- [x] 采集日志记录
- [x] 联络计划独立模块，执行后同步日常联络
- [x] 全局搜索按钮式 + 页面表格化 + 排序

---

## 八、待办与说明

1. **风鸟网/天眼查/企查查**：已实现通用来源框架与账号 Cookie 配置能力，但此类站点需登录态且强反爬，需提供账号/登录 Cookie 后接入实测
2. **定时自动采集**：当前采集为手动触发（详情页按钮 + 设置页批量），每日定时自动采集可后续按配置时间加入（APScheduler 依赖已就绪）
3. **采集信息编辑**：支持删除，未提供正文编辑（新闻原文以链接为准）
4. AI 抽取/分析依赖本机模型服务（LM Studio，端口 1234），模型未启动时采集/分析返回明确错误提示，不影响系统其他功能
