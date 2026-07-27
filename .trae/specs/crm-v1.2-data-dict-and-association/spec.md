# CRM v1.2 数据字典与数据关联加固 Spec

## Why
CRM-v1.1 现有 68 条自动化测试全部通过，但围绕"数据关联"与"操作便利性"存在系统性缺陷：客户类型/级别/阶段等关键字段为自由文本录入（无数据字典），客户、联系人在各表单中未做级联选取导致数据无法关联，列表无分页、下拉无搜索导致数据量增长后不可用，且存在多个功能失效的 Bug（加入看板不生效、删除卡片走错端点、客户类型更新不落库等）。本变更通过引入数据字典、统一关联选取、补充分页与可搜索下拉、修复失效功能，使整体业务逻辑（线索→商机→联系人→客户）真正闭环。

## What Changes
- **新增数据字典模块**：新增 `DataDictionary` 模型（category + key + label + sort_order + is_active），提供 CRUD API 与设置页管理界面；客户类型/级别/来源/区域、联系人重要性、活动方式、商机阶段等下拉项全部改由数据字典驱动。
- **统一关联选取**：所有表单中"客户""联系人"字段一律改为下拉选择（不得录入）；联系人下拉按已选客户级联过滤；线索转化商机时预填线索已有客户并级联联系人。
- **分页与可搜索下拉**：列表接口统一支持 `page/page_size` 服务端分页与总数返回；客户/联系人下拉长度超过阈值时启用"下拉搜索"组件（输入过滤 + 滚动）。
- **表单字段完善**：联系人表单补齐 `importance`、`business_scope`；活动表单补齐 `opportunity_id`、`lead_id` 选取；商机阶段、阶段记录阶段名改由 `OpportunityStage` 字典选取；客户表单类型/级别/来源/区域改下拉。
- **修复失效功能**：
  - 修复"加入看板"不生效：阶段记录/活动/跟进勾选 `add_to_kanban` 时真实创建 `KanbanCard`。
  - 修复看板卡片删除：新增 `DELETE /api/kanban/cards/<id>` 端点，前端改用正确端点。
  - 修复看板卡片新建：新增 `POST /api/kanban/columns/<col_id>/cards`，按所选列添加。
  - 修复客户类型更新不落库：统一 API 字段名（`type`↔`customer_type`）。
  - 修复联系人列表"公司"列恒为 `-`：前端读取 `customer_name`。
  - 新增阶段管理 UI（设置页内）调用既有 `/stages` API。
- **Web 界面规范合规**：修复 `transition: all`、补 `aria-live`/`aria-label`、模态框 `overscroll-behavior` + ESC 关闭 + 焦点管理、表单 `name`/`autocomplete`/正确 `type` 与 `inputmode`、占位符 `…`、破坏性操作改用确认模态。

## Impact
- Affected specs: 客户管理、线索管理、商机管理、联系人管理、活动记录、跟进提醒、看板管理、系统设置（新增数据字典子模块）
- Affected code:
  - 后端：[app/models/__init__.py](file:///workspace/app/models/__init__.py)（新增 DataDictionary 模型）、[app/routes/api.py](file:///workspace/app/routes/api.py)（字典 API、分页、级联过滤、看板卡片 CRUD、加入看板逻辑、字段名修复）
  - 服务：[app/services/seed.py](file:///workspace/app/services/seed.py)（字典种子数据）、[app/services/suggestion_engine.py](file:///workspace/app/services/suggestion_engine.py)
  - 前端：[app/static/index.html](file:///workspace/app/static/index.html)（全部表单、列表、看板、设置页）
  - 测试：[tests/test_aics.py](file:///workspace/tests/test_aics.py)（补充字典、分页、级联、看板、关联字段用例）

## ADDED Requirements

### Requirement: 数据字典管理
系统 SHALL 提供统一的数据字典模块，用于集中维护各业务实体的枚举型下拉选项。

#### Scenario: 字典分类与选项维护
- **WHEN** 管理员在「系统设置 → 数据字典」中新增/编辑/停用某分类（如 customer_type、customer_level、customer_source、region、contact_importance、activity_method、opportunity_stage）下的选项
- **THEN** 该选项立即对所有业务表单对应字段生效，无需改代码

#### Scenario: 字典驱动下拉
- **WHEN** 用户打开任一业务表单（客户/联系人/商机/活动/跟进）
- **THEN** 类型、级别、来源、区域、重要性、方式、阶段等枚举字段 SHALL 渲染为下拉，选项来自对应字典分类的启用项，按 sort_order 排序

#### Scenario: 字典 API
- **WHEN** 前端请求 `GET /api/dictionary?category=<cat>`
- **THEN** 返回该分类下所有启用选项（id/key/label/sort_order）
- **WHEN** 请求 `GET /api/dictionary`（无 category）
- **THEN** 返回全部分类及其选项，供设置页管理

### Requirement: 关联字段级联选取
所有引用客户/联系人的表单 SHALL 使用下拉选取（不得录入），且联系人下拉按已选客户级联过滤。

#### Scenario: 联系人按客户级联
- **WHEN** 用户在活动/商机/跟进/线索转化表单中选定客户 A
- **THEN** 联系人下拉 SHALL 仅显示归属于客户 A 的联系人；切换客户时联系人下拉同步刷新

#### Scenario: 线索转化预填与级联
- **WHEN** 用户对一条已关联客户 C 的线索点击「转商机」
- **THEN** 商机表单客户下拉 SHALL 默认选中客户 C，联系人下拉 SHALL 级联显示客户 C 的联系人

#### Scenario: 客户为唯一维护点
- **WHEN** 用户在联系人/商机/活动/跟进表单中需要指定客户
- **THEN** SHALL 通过下拉从既有客户中选取；系统 SHALL 禁止在非客户表单中新增客户名称文本

### Requirement: 服务端分页
所有列表接口 SHALL 支持服务端分页，避免一次性返回全量数据。

#### Scenario: 分页参数
- **WHEN** 前端请求 `GET /api/<resource>?page=2&page_size=20`
- **THEN** 返回第 2 页（每页 20 条）数据，并在响应中包含 `total`（总条数）与 `page`/`page_size`
- **WHEN** 不传分页参数
- **THEN** 使用默认 page=1、page_size=20

#### Scenario: 分页 UI
- **WHEN** 列表数据总数大于当前页大小
- **THEN** 列表底部 SHALL 显示分页控件（上一页/下一页/页码），并保留当前搜索与筛选条件

### Requirement: 可搜索下拉
当候选下拉项数量较多时 SHALL 提供下拉内搜索能力。

#### Scenario: 客户/联系人下拉搜索
- **WHEN** 客户或联系人下拉项超过 20 个
- **THEN** 下拉 SHALL 支持输入关键字过滤（按名称/简称/电话匹配），并限制最大可视高度支持滚动

### Requirement: 加入看板联动
当业务记录勾选"加入看板"时 SHALL 真实在看板创建卡片。

#### Scenario: 阶段/活动/跟进加入看板
- **WHEN** 用户创建阶段记录/活动/跟进时勾选「加入看板」并选择目标看板
- **THEN** 系统 SHALL 在该看板首列创建一张 KanbanCard，title 取自业务记录，source_type/source_id 指向来源记录

### Requirement: 看板卡片完整 CRUD
看板卡片 SHALL 支持在指定列新建、删除、移动。

#### Scenario: 指定列新建卡片
- **WHEN** 用户在某列点击「+ 添加卡片」并提交
- **THEN** 卡片 SHALL 创建于该列（而非固定落到首列）

#### Scenario: 删除卡片
- **WHEN** 用户点击卡片「删除」并确认
- **THEN** 系统 SHALL 调用 `DELETE /api/kanban/cards/<id>` 删除该卡片（而非复用 move 端点）

## MODIFIED Requirements

### Requirement: 客户管理表单
客户表单的类型、级别、来源、区域字段 SHALL 由自由文本输入改为数据字典驱动的下拉选择；更新接口 SHALL 正确持久化 `customer_type` 字段。

#### Scenario: 客户类型更新落库
- **WHEN** 用户编辑客户并选择新的客户类型后保存
- **THEN** `PUT /api/customers/<id>` SHALL 将类型写入 `customer_type` 字段并持久化（修复前端发 `type` 而后端读 `customer_type` 的不一致）

### Requirement: 联系人管理表单
联系人表单 SHALL 暴露 `importance`、`business_scope` 字段（下拉/文本），并正确显示所属客户名称。

#### Scenario: 联系人列表公司列
- **WHEN** 联系人列表渲染「公司」列
- **THEN** SHALL 读取 `customer_name` 字段显示所属客户名（修复读取 `company` 恒为 `-` 的 Bug）

### Requirement: 商机与阶段管理
商机表单的当前阶段 SHALL 由 `OpportunityStage` 字典下拉选取；阶段记录的阶段名 SHALL 由阶段字典选取；设置页 SHALL 提供阶段字典管理 UI 调用既有 `/stages` API。

### Requirement: 活动表单关联
活动表单 SHALL 提供商机、线索下拉选取（与客户/联系人同级联），保证活动可挂载到完整业务链路。

## REMOVED Requirements
（本变更不移除既有功能，仅修复与增强。）

## 附：Web Interface Guidelines 合规要点（一并修复）
- 移除 `transition: all`，改为显式属性列表
- Toast 增加 `aria-live="polite"`
- 图标按钮（移动端菜单、爬虫按钮）补 `aria-label`
- 模态框增加 `overscroll-behavior: contain`、ESC 关闭、打开时聚焦、关闭后归还焦点
- 表单输入补 `name` 与 `autocomplete`；电话用 `type="tel" inputmode="tel"`、网址用 `type="url"`、邮箱 `autocomplete="email"`
- 占位符 `...` 统一为 `…`；加载态统一 `…`
- 破坏性操作由原生 `confirm()`/`prompt()` 改为确认模态
- 数字列（预算、金额、计数）应用 `font-variant-numeric: tabular-nums`
- 列表筛选/分页状态同步至 URL hash/query，支持刷新保留
