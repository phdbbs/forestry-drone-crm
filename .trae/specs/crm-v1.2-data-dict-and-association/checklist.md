# Checklist

## 数据字典
- [x] DataDictionary 模型已创建（含 category/item_key/label/sort_order/is_active，唯一约束）
- [x] 字典 CRUD API（GET 全量/单分类、POST、PUT、DELETE、停用）已实现
- [x] 客户类型/级别/来源/区域、联系人重要性、活动方式、商机阶段种子数据已写入
- [x] 设置页数据字典管理 UI 可增/改/停用/删除选项
- [x] 所有业务表单枚举字段均由字典下拉驱动（无自由文本录入）

## 数据关联
- [x] 客户表单类型/级别/来源/区域为下拉选择
- [x] 活动/商机/跟进/线索转化表单中联系人下拉按已选客户级联过滤
- [x] 线索转化预填线索已有客户并级联联系人
- [x] 活动表单提供商机、线索下拉（按客户过滤）
- [x] 商机当前阶段、阶段记录阶段名由 OpportunityStage 字典选取
- [x] 联系人表单补齐 importance、business_scope 字段
- [x] 客户为唯一维护点：非客户表单禁止录入客户名称文本

## 分页与可搜索下拉
- [x] 所有列表接口支持 page/page_size 并返回 total/page/page_size
- [x] 前端列表显示分页控件并保留搜索/筛选条件
- [x] 客户/联系人下拉项 >20 时启用下拉内搜索（输入过滤 + 滚动）
- [x] 阶段记录/活动/跟进加入看板时可选目标看板

## 功能 Bug 修复
- [x] 勾选"加入看板"真实创建 KanbanCard（阶段记录/活动/跟进三处均验证）
- [x] 新增 POST /api/kanban/columns/<col_id>/cards，卡片按所选列创建
- [x] 新增 DELETE /api/kanban/cards/<id>，前端 deleteCard 改用正确端点
- [x] 客户类型更新正确落库（前后端字段名一致）
- [x] 联系人列表"公司"列读取 customer_name 显示（不再恒为 `-`）
- [x] list_opportunities / list_boards 服务端 search 生效
- [x] 设置页阶段管理 UI 调用既有 /stages API

## Web Interface Guidelines 合规
- [x] CSS 中无 `transition: all`（改为显式属性）
- [x] Toast 容器具备 aria-live="polite"
- [x] 图标按钮具备 aria-label
- [x] 模态框具备 overscroll-behavior: contain、ESC 关闭、焦点管理
- [x] 表单输入具备 name 与 autocomplete；电话/网址/邮箱使用正确 type/inputmode
- [x] 占位符与加载态使用 `…` 而非 `...`
- [x] 数字列具备 font-variant-numeric: tabular-nums
- [x] 破坏性操作使用确认模态而非原生 confirm()/prompt()
- [x] 列表搜索/筛选/分页状态同步至 URL

## 测试
- [x] 现有 68 条 AICS 用例全部通过（无回归）
- [ ] 新增字典、分页、级联、看板联动、看板卡片 CRUD、字段回归用例全部通过
- [x] 应用可正常启动（instance 目录自动创建，无 DB 打开错误）
