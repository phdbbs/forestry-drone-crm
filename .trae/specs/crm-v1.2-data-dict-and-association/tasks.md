# Tasks

## 阶段一：数据字典与模型基础
- [x] Task 1: 新增 DataDictionary 模型与种子数据
  - [x] SubTask 1.1: 在 [app/models/__init__.py](file:///workspace/app/models/__init__.py) 新增 `DataDictionary` 模型（id, category, item_key, label, sort_order, is_active, created_at, updated_at），并补充唯一约束 (category, item_key)
  - [x] SubTask 1.2: 在 [app/services/seed.py](file:///workspace/app/services/seed.py) 为 customer_type/customer_level/customer_source/region/contact_importance/activity_method/opportunity_stage 各分类写入种子选项（沿用现有 seed 中的"政府/运营商/科技公司/科研院所"、"省级"、"高匹配/中匹配/低匹配"等既有取值，并补全活动方式"电话/拜访/微信/邮件/会议"、联系人重要性"关键/重要/一般"）
  - [x] SubTask 1.3: 新增字典 CRUD API：`GET /api/dictionary`（全量按分类分组）、`GET /api/dictionary?category=<cat>`（单分类启用项）、`POST/PUT/DELETE /api/dictionary` 与 `/api/dictionary/<id>`，停用走 `is_active=False`

## 阶段二：后端关联、分页与字段修复
- [x] Task 2: 统一列表接口服务端分页与字段修复
  - [x] SubTask 2.1: 为 customers/leads/opportunities/contacts/activities/followups 列表接口增加 `page`/`page_size` 参数（默认 1/20），响应改为 `{data:[...], total, page, page_size}`；保持无分页参数时兼容（前端逐步切换）
  - [x] SubTask 2.2: `GET /api/customers` 支持 `customer_id` 批量与按客户返回其联系人 `GET /api/contacts?customer_id=<id>`（级联过滤用）
  - [x] SubTask 2.3: 修复 `update_customer` 字段不一致：接受前端 `type` 并映射到 `customer_type`（或前端统一发 `customer_type`，二选一，保持前后端一致），确保类型/级别更新落库
  - [x] SubTask 2.4: 修复 `list_opportunities`/`list_boards` 忽略 `search` 参数：补全服务端搜索（按标题/名称匹配）
- [x] Task 3: 修复"加入看板"联动与看板卡片 CRUD
  - [x] SubTask 3.1: 新增 `POST /api/kanban/columns/<col_id>/cards` 按指定列创建卡片
  - [x] SubTask 3.2: 新增 `DELETE /api/kanban/cards/<id>` 删除卡片
  - [x] SubTask 3.3: 在 `add_stage_record`/`create_activity`/`create_followup` 中，当 `add_to_kanban=True` 且给定 `board_id` 时，创建 `KanbanCard`（title 来自记录、source_type/source_id 关联来源）
- [x] Task 4: 线索转化与级联预填
  - [x] SubTask 4.1: `convert_lead` 当请求未显式给 `customer_id` 时使用 `l.customer_id` 预填；`contact_id` 校验属于该客户（否则忽略），确保转化后商机关联客户与该客户联系人

## 阶段三：前端表单字段选取与级联
- [x] Task 5: 客户表单字典化与列表分页
  - [x] SubTask 5.1: [app/static/index.html](file:///workspace/app/static/index.html) 客户表单类型/级别/来源/区域改为 `<select>`，选项来自 `GET /api/dictionary?category=<cat>`
  - [x] SubTask 5.2: 客户表单保存统一发送 `customer_type`（与后端一致），修复类型不落库
  - [x] SubTask 5.3: 客户列表接入服务端分页（page/page_size + 分页控件），搜索改服务端
- [x] Task 6: 联系人表单完善与级联
  - [x] SubTask 6.1: 联系人表单补 `importance`（字典下拉）与 `business_scope`（文本域）
  - [x] SubTask 6.2: 联系人列表"公司"列改读 `customer_name`，修复恒为 `-`
  - [x] SubTask 6.3: 联系人列表接入服务端分页
- [x] Task 7: 活动/商机/跟进表单级联与字段补齐
  - [x] SubTask 7.1: 在活动/商机/跟进/线索转化表单中，选定客户后调用 `GET /api/contacts?customer_id=<id>` 刷新联系人下拉（级联过滤），切换客户清空联系人选择
  - [x] SubTask 7.2: 线索转化表单预填线索已有 `customer_id` 并级联联系人
  - [x] SubTask 7.3: 活动表单补 `opportunity_id`、`lead_id` 下拉选取（按已选客户过滤商机/线索）
  - [x] SubTask 7.4: 商机表单 `current_stage` 与阶段记录 `stage_name` 改为 `OpportunityStage` 字典下拉
- [x] Task 8: 可搜索下拉组件
  - [x] SubTask 8.1: 实现可复用 `searchableSelect` 组件（输入框 + 下拉过滤 + 最大高度滚动），候选 > 20 项时启用
  - [x] SubTask 8.2: 客户/联系人下拉替换为 `searchableSelect`；阶段记录/活动"加入看板"增加目标看板选择

## 阶段四：设置页数据字典与阶段管理 UI
- [x] Task 9: 设置页数据字典与阶段管理
  - [x] SubTask 9.1: 设置页新增「数据字典」卡片：按分类展示选项列表，支持增/改/停用/删除，调用 `/api/dictionary`
  - [x] SubTask 9.2: 设置页新增「商机阶段管理」卡片：列表 + 增/删/排序，调用既有 `/api/stages`

## 阶段五：看板与功能 Bug 修复（前端）
- [x] Task 10: 看板前端修复与完善
  - [x] SubTask 10.1: `saveCard` 改用 `POST /api/kanban/columns/<col_id>/cards`，按所选列创建
  - [x] SubTask 10.2: `deleteCard` 改用 `DELETE /api/kanban/cards/<id>`
  - [x] SubTask 10.3: 阶段记录/活动/跟进表单的"加入看板"勾选后显示目标看板下拉

## 阶段六：Web Interface Guidelines 合规
- [x] Task 11: 可访问性与表单合规
  - [x] SubTask 11.1: 移除 CSS 中 `transition: all`，改为显式属性（如 `transition: background-color .2s, color .2s`）
  - [x] SubTask 11.2: Toast 容器加 `aria-live="polite"`；图标按钮（mobileToggle、爬虫按钮）补 `aria-label`
  - [x] SubTask 11.3: 模态框加 `overscroll-behavior: contain`、ESC 关闭、打开聚焦首个可交互元素、关闭归还焦点
  - [x] SubTask 11.4: 表单输入补 `name` 与 `autocomplete`；电话 `type="tel" inputmode="tel"`、网址 `type="url"`、邮箱 `autocomplete="email"`
  - [x] SubTask 11.5: 占位符与加载态 `...` 统一为 `…`；数字列加 `font-variant-numeric: tabular-nums`
  - [x] SubTask 11.6: 破坏性操作（删除客户/线索/商机/联系人/活动/跟进/看板/卡片）由 `confirm()`/`prompt()` 改为确认模态
- [x] Task 12: 状态同步至 URL
  - [x] SubTask 12.1: 列表搜索/筛选/分页状态同步至 URL hash query，刷新与分享可还原

## 阶段七：测试补充
- [x] Task 13: 扩充 AICS 测试覆盖新能力与回归
  - [x] SubTask 13.1: 数据字典 CRUD 与字典驱动下拉用例（AICS-M013）
  - [x] SubTask 13.2: 服务端分页与 total 返回用例（AICS-M014）
  - [x] SubTask 13.3: 联系人按客户级联过滤用例（AICS-M015）
  - [x] SubTask 13.4: 加入看板联动真实创建卡片用例（AICS-M016）
  - [x] SubTask 13.5: 看板卡片按列新建/删除用例（AICS-M017）
  - [x] SubTask 13.6: 客户类型更新落库、联系人公司列字段回归用例（AICS-M018）

# Task Dependencies
- [Task 2] 依赖 [Task 1]（字典种子先行，列表分页独立但字段修复需字典）
- [Task 3] 与 [Task 4] 互相独立，可并行
- [Task 5][Task 6][Task 7][Task 8] 前端表单改造依赖 [Task 1]（字典 API）与 [Task 2]（分页/级联接口）；[Task 8] 可被 [Task 5][Task 7] 复用，建议先做 [Task 8]
- [Task 9] 依赖 [Task 1]
- [Task 10] 依赖 [Task 3]
- [Task 13] 依赖全部功能 Task 完成
