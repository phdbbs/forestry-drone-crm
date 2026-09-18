# 林业无人机 CRM 系统 — 测试与修复报告

- **报告日期**：2026-09-18
- **被测系统**：`/Volumes/M4/CRM`（Flask 3.1 + Flask-SQLAlchemy 3.1 + SQLite + Vue3/Vite SPA）
- **需求基线**：`pr-codex.md`（V1.2，2026-07-29）、`crm_3.1_pr.md`（V3.1，2026-08-06）、`林业无人机CRM系统.html`（原型）
- **测试结论**：**292 条用例全部通过**；累计修复 **18 处生产缺陷**（本轮 7 处 + 前序 11 处），补全 **4 处接口字段契约**

---

## 一、重要前提：原工作区只读

`/Volumes/M4/CRM` 挂载自 SMB 网络卷（`//100.99.98.4/M4`），**对本机只读**：

```
$ touch /Volumes/M4/CRM/.write_test
touch: .write_test: Operation not permitted
```

因此全部工作（备份、修复、测试）在**同卷可写副本** `/Volumes/M4/CRM_work/` 中完成，
并以补丁形式提供同步手段（见第六节）。**原始工程与原始数据库均未被修改**：

```
b0c7026421a2b5c04266c11d4097b3a8b154e4a8ec6f6c5304be51661e4c3a58  /Volumes/M4/CRM/instance/crm.db
b0c7026421a2b5c04266c11d4097b3a8b154e4a8ec6f6c5304be51661e4c3a58  CRM_work/instance/crm.db
b0c7026421a2b5c04266c11d4097b3a8b154e4a8ec6f6c5304be51661e4c3a58  CRM_work/backups/crm_backup_20260918_200319.db
b0c7026421a2b5c04266c11d4097b3a8b154e4a8ec6f6c5304be51661e4c3a58  /Volumes/M4/CRM_backups/crm_backup_20260918_200319.db
```

---

## 二、数据库备份与校验

| 项目 | 结果 |
| --- | --- |
| 备份文件 1 | `/Volumes/M4/CRM_work/backups/crm_backup_20260918_200319.db` |
| 备份文件 2 | `/Volumes/M4/CRM_backups/crm_backup_20260918_200319.db`（独立目录，异盘冗余） |
| 文件大小 | 765,952 字节 |
| `PRAGMA integrity_check` | **ok** |
| SHA-256 | `b0c70264…1e4c3a58`（与原库逐字节一致） |

**数据量快照（16 张表）**

| 表 | 行数 | 表 | 行数 |
| --- | ---: | --- | ---: |
| leads | 251 | opportunities | 15 |
| customers | 27 | kanban_columns | 7 |
| contacts | 18 | activities | 4 |
| system_config | 14 | kanban_cards | 4 |
| kanban_boards | 2 | followups | 2 |
| crawl_logs | 1 | stage_records | 1 |
| contact_news / customer_news / opportunity_stages / skills | 0 | | |

**数据健康检查**：17 项检查全部为 0 异常（14 类孤儿引用 + 空标题 / 空客户名 / 空联系人名）。

---

## 三、测试套件结构（292 条）

| 套件 | 文件 | 条数 | 定位 |
| --- | --- | ---: | --- |
| AICS 集成 | `tests/test_aics.py` | **130** | 按需求文档 M001–M015 模块组织的端到端接口用例 |
| EDGE 边界 | `tests/test_edge_cases.py` | **82** | 输入校验、状态机、关联完整性、看板联动、空库极端、健壮性冒烟 |
| UNIT 单元 | `tests/test_services.py` | **80** | 服务层纯逻辑：匹配度 / 流水号 / 行政区划 / 爬虫解析 / AI 容错 / 新闻采集 |
| 真实库冒烟 | `tests/smoke_real_db.py` | 脚本 | 对真实库副本跑主链路，兜住"真实数据才暴露"的问题 |

**AICS 模块分布（130）**

| 模块 | 条数 | 模块 | 条数 |
| --- | ---: | --- | ---: |
| M001 客户管理 | 8 | M009 联络计划 | 9 |
| M002 线索管理 | 17 | M010 工作台 | 7 |
| M003 商机管理 | 11 | M011 数据采集 | 9 |
| M004 联系人管理 | 6 | M012 接口契约 | 6 |
| M005 活动记录 | 11 | M013 数据报表 | 6 |
| M006 看板管理 | 11 | M014 数据导出 | 10 |
| M007 系统设置 | 8 | M015 公告全文 | 6 |
| M008 智能建议 | 5 | | |

**EDGE 分组（82）**

| 分组 | 条数 | 分组 | 条数 |
| --- | ---: | --- | ---: |
| EDGE-01 输入校验 | 15 | EDGE-05 跟进同步 | 4 |
| EDGE-02 状态机 | 10 | EDGE-06 统计口径 | 8 |
| EDGE-03 关联完整性 | 6 | EDGE-07 空库极端 | 5 |
| EDGE-04 看板联动 | 10 | EDGE-08 健壮性冒烟（参数化） | 24 |

**UNIT 分组（80）**

| 分组 | 条数 | 分组 | 条数 |
| --- | ---: | --- | ---: |
| UNIT-01 匹配度 | 7 | UNIT-05 AI 客户端 | 13 |
| UNIT-02 流水号 | 13 | UNIT-06 新闻采集 | 10 |
| UNIT-03 行政区划 | 8 | UNIT-07 技能与建议 | 5 |
| UNIT-04 爬虫解析 | 24 | | |

**改造前后对比**：原套件 94 条（AICS 68 + EDGE 26），多为 happy-path、硬编码主键、断言稀疏，存在"假绿"。
现为 292 条真实断言用例，并新增 `conftest.py` 夹具体系与 `crm_test_utils.py` 公共工具。

---

## 四、本轮（继续执行）修复的缺陷

### 4.1 行政区划解析吞掉省份/城市 — `app/services/regions.py`

**根因**：省份用贪婪正则 `[\u4e00-\u9fa5]{2,6}省` 匹配，城市用 `([\u4e00-\u9fa5]{2,6})市` 匹配，二者都会跨越前文。

| 输入 | 修复前 | 修复后 |
| --- | --- | --- |
| `本项目建设地点在福建省` | 省份候选 = `设地点在福建省` | `福建省` |
| `黑龙江省哈尔滨市依兰县` | 城市候选 = `龙江省哈尔滨市` | `哈尔滨市` |
| `内蒙古自治区呼和浩特市新城区` | 城市候选 = `治区呼和浩特市` | `呼和浩特市` |
| **`山东省威海市`** | **`resolve_region` → `山东`（市级丢失）** | **`山东威海`** |

**改法**：省份改为「用离线索引中的全称做锚点定位」，城市匹配前把省份片段用非汉字字符屏蔽，
城市正则改为非贪婪。`山东省威海市` 丢失市级是**用户可见的真实缺陷**（列表地区列会少一级）。

### 4.2 完整地区提取输出格式不一致 — `app/services/crawler.py`

**根因**：`extract_region_full` 的地址路径产出全称（`安徽省合肥市庐阳区`），
标题兜底路径却走 `extract_region()` 的简称（`山东`），拼出 `山东威海市` 这种**简称+全称混排**。

**改法**：新增 `province_full()`（山东→山东省、内蒙古→内蒙古自治区、北京→北京市），
统一三处兜底路径的输出格式；并修正 `_parse_addr` 把 `万州区` / `通州区` 误当地级市而丢字的问题
（原 `重庆市万州区` → `重庆市万州`，现正确）。

### 4.3 接口错误语义不精确 — `app/__init__.py`

| 问题 | 修复前 | 修复后 |
| --- | --- | --- |
| 路径已注册但方法不符 | `GET /api/export/leads` → **404**（被 SPA 兜底路由抢走） | **405** + 中文文案 |
| 405 错误文案 | 泄漏 Werkzeug 英文 `The method is not allowed for the requested URL.` | `请求方法不被允许` |
| 业务校验提示 | 会被通用文案覆盖 | `abort(400, description=…)` 优先保留（如 `缺少必填字段: name`） |

**改法**：SPA 兜底路由在 `/api/*` 分支内遍历方法查询 URL Map，区分"路径不存在(404)"与"方法不符(405)"；
错误处理器改为「仅当 description 等于 Werkzeug 类默认英文描述时才替换为中文」。

### 4.4 测试代码自身的四处错误（已修正）

| 用例 | 问题 | 修正 |
| --- | --- | --- |
| `test_unit_02_004` | `Lead.query.delete()` 被 `opportunities.lead_id` 外键阻塞 | 改用 `wipe_all(session)` 按依赖顺序清库 |
| `test_unit_03_006` | 断言 `'安徽黄山'.count('黄山') == 2`，与"去重"语义相反 | 改为 `result == '安徽黄山'` 且 `count == 1` |
| `test_unit_05_006` | `SystemConfig` 直接 `add` 与 seed 已有键冲突（`UNIQUE constraint failed`） | 改为 upsert |
| `test_unit_06_007` | `_fetch` 打桩用 `'cggg' in url` 判断，详情页也命中列表分支 | 改为 `url.endswith('/')` 区分列表/详情页 |

### 4.6 数据报表漏斗阶段重复 — `app/routes/api.py`

**发现方式**：启动服务后人工核对 `/api/analytics`，发现漏斗返回 **15 条**，但实际只有 2 个阶段。

**根因**：阶段配置表 `opportunity_stages` 在真实库中为 **0 行**，于是：

```python
configured = []                                            # 配置为空
seen = [o.current_stage for o in opportunities if o.current_stage]   # 未去重
stages_list = configured + [s for s in seen if s not in configured]  # 去重条件恒为真
```

`s not in configured` 在 `configured` 为空时**恒为 True**，`seen` 中的重复阶段被原样保留，
14 条「初步接触」商机 → 14 个同名阶段条目。**前端报表页的漏斗图会画出 15 根柱子，其中 14 根完全相同。**

**修复**：

```python
seen = list(dict.fromkeys(o.current_stage for o in opportunities if o.current_stage))
stages_list = list(dict.fromkeys(configured)) + [s for s in seen if s not in configured]
```

**效果**：`funnel` 从 15 条降为 **2 条**（`初步接触` 14 条 / `方案报价` 1 条），计数与商机总数一致。

**回归用例**：`AICS-M013-006`（`test_m013_006_funnel_stages_unique`）——
已实测验证：回退修复后该用例**变红**，恢复后**变绿**。

### 4.7 前序轮次修复的 11 处缺陷（回归仍全绿）

| # | 缺陷 | 修法 |
| --- | --- | --- |
| 1 | `GET /api/dashboard` 500：`a.content[:80]` 遇 `None` | 新增 `_text()` 归一化 |
| 2 | `GET /api/followups` 500：`source_activity.content[:100]` 遇 `None` | 同上 |
| 3 | `POST /api/kanban/boards/<id>/columns` 500：board 不存在时空值解引用 | 改 `get_or_404` |
| 4 | `POST /api/kanban/import` 500：`items` 为 dict / `[null]` | 类型校验返回 400 |
| 5 | 未注册 `/api/*` 返回 **200 HTML**（SPA 兜底吞掉 404） | 兜底路由前置 JSON 404 |
| 6 | `415 Unsupported Media Type` 返回 HTML | 注册 415 处理器 |
| 7 | **外键悬空可写入**（`customer_id=99999` 返回 200） | `PRAGMA foreign_keys=ON` + `IntegrityError` 分类提示 |
| 8 | 查询参数非法值被静默忽略（`?customer_id=abc` 返回 200 全量） | `_int_arg()` 统一返回 400 |
| 9 | `name='   '` 可建客户 | 去空格后校验 |
| 10 | `move` 的 `position='abc'` 泄漏内部异常 | 显式整数校验 |
| 11 | `reorder ids='abc'` / `[null]` 静默成功 | 数组元素类型校验 |
| 12 | 接口字段契约缺失 4 处 | 见下 |

**接口字段契约补全**

| 接口 | 补充字段 |
| --- | --- |
| `GET /api/customers/<id>/news` | `source_name`、`event_time`、`crawled_at` |
| `GET /api/leads/<id>` | `match_score`、`reason` |
| `GET /api/contacts/<id>` | `role`、`tags`、`avatar` |
| `GET /api/daily-brief` 的 `today_activities` | `title`、`content` |

---

## 五、验证方式与结果

### 5.1 单元/集成/边界套件

```bash
cd /Volumes/M4/CRM_work
/Users/wl-macbookair/.workbuddy-ai/binaries/python/envs/crm-test/bin/python \
  -m pytest tests/ -q -p no:cacheprovider
# 292 passed
```

### 5.2 真实数据库副本冒烟

```bash
cd /Volumes/M4/CRM_work
/Users/wl-macbookair/.workbuddy-ai/binaries/python/envs/crm-test/bin/python \
  tests/smoke_real_db.py
# 冒烟通过：主链路无 5xx、无 HTML、错误语义正确
```

覆盖 24 个列表/聚合接口、6 个导出接口、5 个详情接口，以及 11 项错误语义断言
（404 路径不存在 / 405 方法不符 / 400 参数非法与缺必填 / 400 外键悬空 / 415 非 JSON 请求体）。

### 5.3 行政区划真实公告文本回归

用 10 条含"页脚省份干扰、省市县全称简称混排"的真实公告片段校验，**10/10 与预期一致**：

```
OK 浙江省丽水市遂昌县林业局无人机采购项目  -> 浙江丽水遂昌
OK 重庆市 长寿区 邻封镇 松材线虫病防治    -> 重庆长寿
OK 新疆巴音郭楞蒙古自治州库尔勒市无人机巡检 -> 新疆巴音郭楞库尔勒
OK 本公告由 北京市 朝阳区 园林绿化局发布   -> 北京朝阳
...
一致 10 / 差异 0
```

### 5.4 测试环境

- venv：`/Users/wl-macbookair/.workbuddy-ai/binaries/python/envs/crm-test`（Python 3.13.12）
- 依赖：Flask 3.1.3、Flask-SQLAlchemy 3.1.1、SQLAlchemy 2.0.54、Werkzeug 3.1.8、requests 2.34.2、beautifulsoup4 4.15.0、APScheduler 3.11.3、pytest 9.1.1

### 5.5 本地启动（人工验证）

```bash
cd /Volumes/M4/CRM_work
CRM_PORT=5001 /Users/wl-macbookair/.workbuddy-ai/binaries/python/envs/crm-test/bin/python run_local.py
# 访问 http://127.0.0.1:5001
```

`run_local.py` 仅监听回环地址 `127.0.0.1`（项目自带 `app.py` 绑定 `0.0.0.0`，会对外暴露），
并关闭 `use_reloader`，避免验证时进程被重载打断。使用的工作副本数据库为真实库副本
（251 条线索 / 27 客户 / 15 商机）。

### 5.6 人工验证清单

打开 `http://127.0.0.1:5001` 后，建议按下面顺序核对（括号内为修复项）：

| # | 操作 | 期望 |
| --- | --- | --- |
| 1 | 打开首页 | 正常渲染 Vue 界面，无空白、无控制台报错 |
| 2 | 工作台（Dashboard） | 统计卡显示：待转化线索 **199**、商机 **15**、紧急线索 **25**、今日联络 0 |
| 3 | 数据报表 → 销售漏斗 | 只有 **2 个阶段**：初步接触 14 / 方案报价 1（**修复前会画出 15 根柱子**） |
| 4 | 数据报表 → 月度趋势 | 最近 6 个月：8 月 **86** 条、9 月 **165** 条（合计 251，与线索总数一致） |
| 5 | 线索管理 → 地区列 | 显示形如 `浙江丽水遂昌` 的两级以上地区（**修复前只有省市时可能只剩 `山东`**） |
| 6 | 线索管理 → 按地区搜索「浙江」 | 能筛出浙江线索 |
| 7 | 客户管理 → 详情 → 动态信息 | 字段完整，无 `undefined` |
| 8 | 任意列表 → 导出 CSV | 下载成功，用 Excel 打开中文不乱码（UTF-8 BOM） |
| 9 | 新建客户 → 名称留空/只打空格 | 提示「缺少必填字段: name」，不创建脏数据 |
| 10 | 浏览器地址栏访问 `/api/nonexistent` | 返回 JSON `{"error":"接口不存在"}`，**不是 HTML 页面** |
| 11 | 浏览器地址栏访问 `/api/export/leads`（GET） | 返回 JSON `{"error":"请求方法不被允许"}`（**修复前为 404**） |

第 10、11 项直接在地址栏输入即可，是本次「SPA 兜底吞掉 API 错误」修复的最直观验证。

---

## 六、如何把改动同步回原工程

原工作区只读，改动以补丁提供（已用 `patch --dry-run` 验证可干净应用，
且应用后与原改动**逐字节一致**）：

```bash
cd /Volumes/M4/CRM          # 或先把原工程拷贝到本地可写目录
patch -p1 < /Volumes/M4/CRM_work/patches/app.patch         # 4 个生产文件
patch -p1 < /Volumes/M4/CRM_work/patches/tests.patch       # 6 个测试文件（含新增）
patch -p1 < /Volumes/M4/CRM_work/patches/run_local.patch   # 新增本地启动脚本
```

| 补丁 | 内容 |
| --- | --- |
| `patches/app.patch` | `app/__init__.py`、`app/routes/api.py`、`app/services/crawler.py`、`app/services/regions.py` |
| `patches/tests.patch` | `conftest.py`、`crm_test_utils.py`、`smoke_real_db.py`、`test_aics.py`、`test_edge_cases.py`、`test_services.py` |
| `patches/run_local.patch` | `run_local.py`（仅监听 127.0.0.1 的本地启动脚本） |

> `patches/test_aics.patch`、`patches/test_edge_cases.patch` 为早期版本，已被 `tests.patch` 取代（SMB 卷拒绝删除，故置空并标注废弃）。

**若只需可运行工程**：直接使用 `/Volumes/M4/CRM_work/` 整个目录即可，它包含修复后的 `app/`、
完整 `tests/`、`instance/crm.db` 与 `backups/`。

---

## 七、遗留事项与已知限制

1. **`extract_region_full` 目前是死代码**——全仓库仅有定义、无调用（生产链路走 `resolve_region`）。
   本次已修正其内部格式不一致与 `万州区` 丢字问题，但它仍未接入任何流程；建议后续确认是删除还是接入。
2. **SPA 兜底路由与 API 路由的仲裁**：`/<path:path>` 兜底路由允许 `GET`，会与 API 路由产生竞争。
   本次已在兜底分支内主动区分 404/405，语义正确；但它仍是一条"先于框架仲裁"的路径，
   后续若新增路由需留意不要在 `/api/` 下产生歧义。
3. **网络爬虫与 AI 调用在测试中全部打桩**，未做真实外网连通性验证（离线环境无法进行）。
4. **`instance/` 下存在 `crm.db.backup`、`crm.db.wedged-backup` 等历史文件**，未纳入本次范围，
   建议后续人工确认是否可归档。
5. **前端 `frontend/` 构建产物（7630 个文件）未纳入测试范围**，本次为后端 API + 服务层全覆盖。
