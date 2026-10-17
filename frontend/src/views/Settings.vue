<template>
  <div class="page">
    <PageHeader :title="auth.isAdmin ? '系统设置' : '我的口令'" :subtitle="auth.isAdmin ? 'AI 服务、采集任务、日志、技能与账号的一站式配置' : '修改自己的登录口令；系统配置仅管理员可见'" />

    <div class="settings-card">
      <el-tabs v-model="tab">
        <!-- ------------------------------ AI 配置 ------------------------------ -->
        <el-tab-pane v-if="auth.isAdmin" label="AI 配置" name="ai">
          <div class="tab-body">
            <div class="ai-toolbar">
              <div class="note-box note-box--inline">
                列表顺序即「轮换 + 故障切换」次序：调用时轮流从不同服务起步以分摊各家额度；某家<b>鉴权失败 / 额度不足 / 连不上 / 不可用</b>时自动切到下一家，全部失败才报错。增删改会自动保存。
              </div>
              <div class="ai-toolbar-actions">
                <el-button :icon="Plus" @click="openProviderForm()">添加一家</el-button>
                <el-button type="primary" :loading="aiSaving" @click="saveProviders">保存配置</el-button>
              </div>
            </div>

            <div class="table-wrap">
              <PageTable
                storage-key="ai_providers" :data="providers" :reorderable="false" :show-footer="false"
                empty-text="还没有配置模型服务" empty-hint="点「添加一家」接入第一个模型，可再加多家做轮换容错"
              >
                <template #empty-action>
                  <el-button type="primary" plain size="small" :icon="Plus" @click="openProviderForm()" style="margin-top:12px">添加一家</el-button>
                </template>

                <el-table-column label="编号" width="76" align="center">
                  <template #default="{ $index }"><span class="mono serial">{{ String($index + 1).padStart(2, '0') }}</span></template>
                </el-table-column>
                <el-table-column prop="name" label="名称" min-width="150" show-overflow-tooltip>
                  <template #default="{ row }">
                    <span v-if="row.name">{{ row.name }}</span>
                    <span v-else class="dim">未命名</span>
                    <span v-if="row.enabled === false" class="dim"> · 已停用</span>
                  </template>
                </el-table-column>
                <el-table-column prop="endpoint" label="Endpoint" min-width="250" show-overflow-tooltip>
                  <template #default="{ row }"><span class="mono dim">{{ row.endpoint || '—' }}</span></template>
                </el-table-column>
                <el-table-column label="API Key" min-width="130">
                  <template #default="{ row }">
                    <span v-if="row.has_key" class="mono">{{ row.key_masked }}</span>
                    <span v-else class="is-bad">未配置</span>
                  </template>
                </el-table-column>
                <el-table-column prop="model" label="模型名称" min-width="150" show-overflow-tooltip>
                  <template #default="{ row }"><span class="mono">{{ row.model || '—' }}</span></template>
                </el-table-column>
                <el-table-column label="操作" width="168" fixed="right" align="right">
                  <template #default="{ row, $index }">
                    <div class="row-actions">
                      <el-button link size="small" :loading="row.verifying" @click="verifyRow($index)">验证</el-button>
                      <el-button link size="small" @click="openProviderForm($index)">修改</el-button>
                      <el-button link type="danger" size="small" @click="removeProvider($index)">删除</el-button>
                    </div>
                  </template>
                </el-table-column>
              </PageTable>
            </div>

            <div class="ai-count muted">共 {{ providers.length }} 家，已启用 {{ enabledCount }} 家</div>

            <!-- 添加 / 修改 模型服务 -->
            <el-dialog v-model="providerFormVisible" :title="providerEditIndex === null ? '添加模型服务' : '修改模型服务'" width="580px" destroy-on-close>
              <el-form label-width="104px">
                <el-form-item label="服务名称">
                  <el-input v-model="pform.name" placeholder="如 深度求索 / 本地 Qwen" />
                </el-form-item>
                <el-form-item label="API Endpoint" required>
                  <el-input v-model="pform.endpoint" class="mi" placeholder="https://api.openai.com/v1" />
                </el-form-item>
                <el-form-item label="模型名称" required>
                  <el-input v-model="pform.model" class="mi" placeholder="如 deepseek-chat" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input
                    v-model="pform.api_key" type="password" show-password class="mi"
                    :placeholder="pform.has_key ? ('已保存 ' + pform.key_masked + '（留空则不变）') : '填入该服务的 API Key'"
                  />
                </el-form-item>
                <el-form-item label="启用">
                  <el-switch v-model="pform.enabled" active-text="参与轮换 / 故障切换" />
                </el-form-item>
                <el-form-item label-width="0">
                  <div class="verify-cell">
                    <el-button :loading="pform.verifying" @click="verifyForm">验证连通</el-button>
                    <span v-if="pform.verify" :class="['verify-result', pform.verify.ok ? 'is-ok' : 'is-bad']">
                      <i class="st-dot" />{{ pform.verify.ok ? '连接正常' : (pform.verify.label || '失败') }}
                    </span>
                  </div>
                </el-form-item>
                <div v-if="pform.verify && !pform.verify.ok && (pform.verify.hint || pform.verify.error)" class="verify-err">
                  {{ pform.verify.label }}：{{ pform.verify.hint || pform.verify.error }}
                </div>
              </el-form>
              <template #footer>
                <el-button @click="providerFormVisible = false">取消</el-button>
                <el-button type="primary" @click="commitProviderForm">保存</el-button>
              </template>
            </el-dialog>
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 采集配置 ------------------------------ -->
        <el-tab-pane v-if="auth.isAdmin" label="采集配置" name="crawl">
          <div class="tab-body">
            <div class="form-section sched-card">
              <div class="section-title">定时任务</div>
              <el-row :gutter="14">
                <el-col :span="12">
                  <div class="sched-item">
                    <div class="sched-line">
                      <span class="sched-name">定时采集</span>
                      <el-tag size="small" :type="sched.crawl.enabled ? 'success' : 'info'">{{ sched.crawl.enabled ? '已启用' : '未启用' }}</el-tag>
                    </div>
                    <div class="sched-meta muted">每日 {{ sched.crawl.time }} 执行 · 下次：{{ sched.crawl.next_run || '—' }}</div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="sched-item">
                    <div class="sched-line">
                      <span class="sched-name">自动备份</span>
                      <el-tag size="small" type="success">每日 {{ sched.backup.schedule.replace('每日 ', '') }}</el-tag>
                    </div>
                    <div class="sched-meta muted">下次：{{ sched.backup.next_run || '—' }} · 保留 {{ sched.backup.keep }} 份</div>
                  </div>
                </el-col>
              </el-row>
              <div style="margin-top:10px;display:flex;align-items:center;gap:10px">
                <el-button size="small" :loading="backuping" @click="backupNow">
                  <el-icon><Download /></el-icon>&nbsp;立即备份
                </el-button>
                <span v-if="backupMsg" class="muted">{{ backupMsg }}</span>
              </div>
              <div v-if="sched.backup.list.length" class="backup-list">
                <div v-for="b in sched.backup.list.slice(0, 5)" :key="b.name" class="backup-row">
                  <span class="mono">{{ b.name }}</span>
                  <span class="muted">{{ b.size_kb }} KB · {{ b.mtime }}</span>
                </div>
              </div>
            </div>
            <el-form ref="crawlFormRef" :model="crawlForm" :rules="crawlRules" label-width="112px" class="form-narrow">
              <div class="form-section">
                <div class="section-title">采集来源</div>
                <el-form-item label="来源列表" prop="sources">
                  <el-input v-model="crawlForm.sources" type="textarea" :rows="6" class="mi" placeholder="每行一条，格式：名称|URL" />
                </el-form-item>
              </div>

              <div class="form-section">
                <div class="section-title">采集参数</div>
                <el-row :gutter="12">
                  <el-col :span="12">
                    <el-form-item label="每次抽取上限">
                      <el-input-number v-model="crawlForm.limit" :min="1" :max="50" controls-position="right" class="w-full" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="上次采集">
                      <el-input v-model="crawlForm.lastAt" readonly class="mi" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="关键词过滤">
                  <el-checkbox v-model="crawlForm.kwFilter">启用关键词过滤（命中少时自动扩大范围）</el-checkbox>
                </el-form-item>
                <el-form-item label="关键词">
                  <el-input v-model="crawlForm.keywords" placeholder="逗号分隔，如：无人机,林业,病虫害" />
                </el-form-item>
              </div>

              <div class="form-section">
                <div class="section-title">执行</div>
                <el-form-item label-width="0">
                  <el-button type="primary" :loading="crawlSaving" @click="saveCrawl">保存采集配置</el-button>
                  <el-button :icon="Lightning" :loading="crawl.running" @click="doCrawl">立即采集</el-button>
                  <el-button :icon="Document" @click="tab = 'logs'">查看采集日志</el-button>
                </el-form-item>
              </div>
            </el-form>

            <div v-if="crawl.running" class="run-state">
              <span class="run-pulse" />
              <span>采集进行中：<b>{{ crawl.phase }}</b>
                <span class="mono">{{ crawl.progress }}/{{ crawl.total || '–' }}</span>
                {{ crawl.current }}，已生成 <b class="mono">{{ crawl.count }}</b> 条
              </span>
            </div>
            <template v-else-if="crawl.message">
              <div class="run-state run-state--ok">上次：{{ crawl.message }}</div>
              <div v-if="crawl.errors.length" class="run-errors">
                <span class="run-errors-title">本次异常（已按类型识别）</span>
                <span v-for="(e, i) in crawl.errors" :key="i" class="st-pill st-pill--danger err-chip">{{ e }}</span>
              </div>
            </template>
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 采集日志 ------------------------------ -->
        <el-tab-pane v-if="auth.isAdmin" :label="logTabLabel" name="logs">
          <div class="tab-body">
            <!-- 概览 -->
            <div class="mini-grid">
              <div class="mini-card">
                <div class="mini-label">采集任务</div>
                <div class="mini-value mono">{{ logStats.total }}</div>
              </div>
              <div class="mini-card">
                <div class="mini-label">新增数据</div>
                <div class="mini-value mono is-ok">{{ logStats.items_total }}</div>
              </div>
              <div class="mini-card">
                <div class="mini-label">异常总数</div>
                <div class="mini-value mono is-bad">{{ logStats.error_total }}</div>
              </div>
              <div class="mini-card">
                <div class="mini-label">成功率</div>
                <div class="mini-value mono">{{ successRate }}</div>
              </div>
            </div>

            <!-- 状态分布 -->
            <div class="chip-bar">
              <span class="bar-label">状态</span>
              <button
                v-for="s in STATUS_LIST"
                :key="s.value"
                type="button"
                :class="['chip', `chip--${s.tag}`, { active: filters.status === s.value }]"
                @click="filters.status = filters.status === s.value ? 'all' : s.value; loadLogs()"
              >{{ s.label }}<span class="chip-n">{{ logStats.by_status[s.value] || 0 }}</span></button>
            </div>

            <!-- 错误类型分布 -->
            <div v-if="logStats.error_types.length" class="chip-bar">
              <span class="bar-label">报错类型</span>
              <el-tooltip v-for="t in logStats.error_types" :key="t.code" :content="typeHint(t.code)" placement="top">
                <button
                  type="button"
                  :class="['chip', `chip--${sevTag(t.severity)}`, { active: filters.error_code === t.code }]"
                  @click="filters.error_code = filters.error_code === t.code ? 'all' : t.code; loadLogs()"
                >{{ t.label }}<span class="chip-n">{{ t.count }}</span></button>
              </el-tooltip>
            </div>

            <!-- 筛选 -->
            <div class="log-filters">
              <el-select v-model="filters.task_type" size="small" class="f-select" @change="loadLogs">
                <el-option label="全部任务" value="all" />
                <el-option v-for="t in taskTypes" :key="t" :label="t" :value="t" />
              </el-select>
              <el-select v-model="filters.status" size="small" class="f-select" @change="loadLogs">
                <el-option label="全部状态" value="all" />
                <el-option v-for="s in STATUS_LIST" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
              <el-select v-model="filters.error_code" size="small" class="f-select wide" @change="loadLogs">
                <el-option label="全部报错类型" value="all" />
                <el-option-group v-for="g in errorTypeGroups" :key="g.category" :label="g.category">
                  <el-option v-for="t in g.items" :key="t.code" :label="t.label" :value="t.code" />
                </el-option-group>
              </el-select>
              <el-select v-model="filters.days" size="small" class="f-select" @change="loadLogs">
                <el-option label="全部时间" value="all" />
                <el-option label="今天" value="today" />
                <el-option label="近 7 天" value="7" />
                <el-option label="近 30 天" value="30" />
              </el-select>
              <el-input
                v-model="filters.q"
                size="small"
                class="f-search"
                placeholder="搜索关键词 / 来源 / 结果信息"
                clearable
                @keyup.enter="loadLogs"
                @clear="loadLogs"
              />
              <el-button size="small" :icon="Search" @click="loadLogs">查询</el-button>
              <el-button size="small" @click="resetFilters">重置</el-button>
              <div class="grow" />
              <el-button size="small" :icon="Refresh" @click="loadLogs">刷新</el-button>
              <el-button size="small" type="danger" plain :icon="Delete" @click="clearLogs">清理日志</el-button>
            </div>

            <!-- 日志表 -->
            <el-table
              v-loading="logsLoading"
              :data="logs"
              size="small"
              row-key="id"
              empty-text="暂无采集日志，可在「采集配置」中点击「立即采集」"
              @expand-change="onExpand"
            >
              <el-table-column type="expand">
                <template #default="{ row }">
                  <div class="detail-wrap">
                    <div v-if="!row._detail" class="muted">加载明细中…</div>
                    <template v-else-if="row._detail.length">
                      <div class="sub-head">本次异常明细（{{ row._detail.length }}）</div>
                      <el-table :data="row._detail" size="small" border class="detail-table">
                        <el-table-column label="报错类型" width="140">
                          <template #default="{ row: d }">
                            <span class="st-pill" :class="'st-pill--' + sevTag(d.severity)">{{ d.label }}</span>
                          </template>
                        </el-table-column>
                        <el-table-column prop="stage" label="阶段" width="110" />
                        <el-table-column prop="target" label="对象" min-width="160" show-overflow-tooltip />
                        <el-table-column prop="raw" label="原始报错" min-width="280" show-overflow-tooltip />
                        <el-table-column prop="hint" label="处理建议" min-width="260" show-overflow-tooltip />
                      </el-table>
                    </template>
                    <div v-else class="muted">本次采集无异常。</div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="开始时间" width="150">
                <template #default="{ row }"><span class="mono cell-time">{{ fmtTime(row.started_at) }}</span></template>
              </el-table-column>
              <el-table-column prop="task_type" label="任务类型" width="110" show-overflow-tooltip />
              <el-table-column label="状态" width="96" align="center">
                <template #default="{ row }">
                  <span class="st-pill" :class="'st-pill--' + statusTag(row.status)">
                    <i class="st-dot" />{{ statusLabel(row.status) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="采集内容" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">{{ row.keywords || row.sources || '—' }}</template>
              </el-table-column>
              <el-table-column label="结果信息" min-width="260" show-overflow-tooltip>
                <template #default="{ row }">{{ row.message || '—' }}</template>
              </el-table-column>
              <el-table-column label="新增" width="72" align="center">
                <template #default="{ row }">
                  <span class="mono" :class="{ 'is-ok': row.items_count > 0 }">{{ row.items_count }}</span>
                </template>
              </el-table-column>
              <el-table-column label="异常" width="200">
                <template #default="{ row }">
                  <template v-if="row.error_types && row.error_types.length">
                    <el-tooltip
                      v-for="t in row.error_types.slice(0, 2)"
                      :key="t.code"
                      :content="typeHint(t.code)"
                      placement="top"
                    >
                      <span class="st-pill sv-inline" :class="'st-pill--' + sevTag(t.severity)">
                        {{ t.label }} <b class="mono">{{ t.count }}</b>
                      </span>
                    </el-tooltip>
                    <span v-if="row.error_types.length > 2" class="muted">+{{ row.error_types.length - 2 }}</span>
                  </template>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="80" align="right">
                <template #default="{ row }"><span class="mono">{{ fmtDuration(row.duration_ms) }}</span></template>
              </el-table-column>
              <el-table-column label="操作" width="72" align="center" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-pagination
              v-if="logTotal > 0"
              class="pager"
              size="small"
              layout="total, sizes, prev, pager, next"
              :total="logTotal"
              :current-page="page"
              :page-size="pageSize"
              :page-sizes="[10, 20, 50]"
              @current-change="(p) => { page = p; loadLogs() }"
              @size-change="(s) => { pageSize = s; page = 1; loadLogs() }"
            />
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 操作日志 ------------------------------ -->
        <el-tab-pane v-if="auth.isAdmin" :label="opTabLabel" name="oplog">
          <div class="tab-body">
            <!-- 概览 -->
            <div class="mini-grid">
              <div class="mini-card">
                <div class="mini-label">今日操作</div>
                <div class="mini-value mono">{{ todayRow.total }}</div>
              </div>
              <div class="mini-card">
                <div class="mini-label">今日写操作</div>
                <div class="mini-value mono is-ok">{{ todayWrites }}</div>
              </div>
              <div class="mini-card">
                <div class="mini-label">近 7 天操作</div>
                <div class="mini-value mono">{{ weekTotal }}</div>
              </div>
              <div class="mini-card">
                <div class="mini-label">近 7 天失败</div>
                <div class="mini-value mono" :class="{ 'is-bad': weekFails > 0 }">{{ weekFails }}</div>
              </div>
            </div>

            <!-- 每日总结 -->
            <div class="section-title oplog-title">
              <span>每日日志总结</span>
              <div class="grow" />
              <el-select v-model="sumDays" size="small" class="f-select" @change="loadSummary">
                <el-option :value="7" label="近 7 天" />
                <el-option :value="30" label="近 30 天" />
                <el-option :value="90" label="近 90 天" />
              </el-select>
              <el-button size="small" :loading="sumGenerating" @click="generateSummary('')">生成今日总结</el-button>
              <el-button size="small" :icon="Refresh" @click="loadSummary">刷新</el-button>
            </div>
            <el-table v-loading="sumLoading" :data="sumPageRows" size="small" row-key="day" empty-text="暂无汇总，可点击「生成今日总结」">
              <el-table-column type="expand">
                <template #default="{ row }">
                  <div class="detail-wrap">
                    <div class="sub-head">{{ row.headline }}</div>
                    <div v-if="Object.keys(row.by_user || {}).length" class="chip-bar">
                      <span class="bar-label">按用户</span>
                      <span v-for="(n, u) in row.by_user" :key="u" class="st-pill st-pill--info">
                        {{ u }} <b class="mono">{{ n }}</b>
                      </span>
                    </div>
                    <div v-if="Object.keys(row.by_module || {}).length" class="chip-bar">
                      <span class="bar-label">按模块</span>
                      <span v-for="(n, m) in row.by_module" :key="m" class="st-pill st-pill--info">
                        {{ m }} <b class="mono">{{ n }}</b>
                      </span>
                    </div>
                    <div v-if="row.total" class="op-actions-row">
                      <el-button link type="primary" size="small" @click="openDayLogs(row.day)">查看这一天明细</el-button>
                      <el-button link type="primary" size="small" @click="generateSummary(row.day)">重新生成这天总结</el-button>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="day" label="日期" width="112" />
              <el-table-column label="总结" min-width="320" show-overflow-tooltip>
                <template #default="{ row }"><span class="summary-text">{{ row.headline }}</span></template>
              </el-table-column>
              <el-table-column label="总数" width="76" align="right">
                <template #default="{ row }"><span class="mono">{{ row.total }}</span></template>
              </el-table-column>
              <el-table-column v-for="a in SUMMARY_ACTIONS" :key="a" :label="a" width="68" align="right">
                <template #default="{ row }">
                  <span class="mono" :class="{ muted: !row.by_action[a] }">{{ row.by_action[a] || 0 }}</span>
                </template>
              </el-table-column>
              <el-table-column label="失败" width="68" align="right">
                <template #default="{ row }">
                  <span class="mono" :class="{ 'is-bad': row.failures > 0 }">{{ row.failures }}</span>
                </template>
              </el-table-column>
              <el-table-column label="账号" width="68" align="right">
                <template #default="{ row }"><span class="mono">{{ row.active_users }}</span></template>
              </el-table-column>
              <el-table-column label="归档" width="82" align="center">
                <template #default="{ row }">
                  <span class="st-pill" :class="row.archived ? 'st-pill--success' : 'st-pill--info'">
                    {{ row.archived ? '已生成' : '未生成' }}
                  </span>
                </template>
              </el-table-column>
            </el-table>

            <el-pagination
              v-if="sumRows.length"
              class="pager"
              size="small"
              layout="total, sizes, prev, pager, next"
              :total="sumRows.length"
              :current-page="sumPage"
              :page-size="sumPageSize"
              :page-sizes="[10, 20, 50]"
              @current-change="(p) => { sumPage = p }"
              @size-change="(s) => { sumPageSize = s; sumPage = 1 }"
            />

            <!-- 明细：动作分布 chips + 筛选 -->
            <div class="section-title oplog-title">
              <span>操作明细</span>
              <div class="grow" />
              <el-button size="small" :icon="Download" @click="exportOpLogs">导出 CSV</el-button>
            </div>
            <div v-if="opStatActions.length" class="chip-bar">
              <span class="bar-label">动作</span>
              <button
                v-for="a in opStatActions"
                :key="a.code"
                type="button"
                :class="['chip', `chip--${opChipTag(a.code)}`, { active: opFilters.action === a.code }]"
                @click="opFilters.action = opFilters.action === a.code ? 'all' : a.code; opPage = 1; loadOpLogs()"
              >{{ a.code }}<span class="chip-n">{{ a.count }}</span></button>
            </div>
            <div class="log-filters">
              <el-select v-model="opFilters.days" size="small" class="f-select" @change="onOpDaysChange">
                <el-option label="今天" value="today" />
                <el-option label="近 7 天" value="7" />
                <el-option label="近 30 天" value="30" />
                <el-option label="近 90 天" value="90" />
                <el-option label="全部时间" value="all" />
              </el-select>
              <el-select v-model="opFilters.user" size="small" class="f-select" clearable placeholder="全部用户" @change="opPage = 1; loadOpLogs()">
                <el-option label="全部用户" value="all" />
                <el-option v-for="u in opEnums.users" :key="u" :label="u" :value="u" />
              </el-select>
              <el-select v-model="opFilters.action" size="small" class="f-select" placeholder="全部操作" @change="opPage = 1; loadOpLogs()">
                <el-option label="全部操作" value="all" />
                <el-option v-for="a in opEnums.actions" :key="a" :label="a" :value="a" />
              </el-select>
              <el-select v-model="opFilters.module" size="small" class="f-select" placeholder="全部模块" @change="opPage = 1; loadOpLogs()">
                <el-option label="全部模块" value="all" />
                <el-option v-for="m in opEnums.modules" :key="m" :label="m" :value="m" />
              </el-select>
              <el-select v-model="opFilters.result" size="small" class="f-select" @change="opPage = 1; loadOpLogs()">
                <el-option label="全部结果" value="all" />
                <el-option label="仅失败" value="fail" />
              </el-select>
              <el-input
                v-model="opFilters.q"
                size="small"
                class="f-search"
                placeholder="搜索操作内容 / 接口 / 用户"
                clearable
                @keyup.enter="opPage = 1; loadOpLogs()"
                @clear="opPage = 1; loadOpLogs()"
              />
              <el-button size="small" :icon="Search" @click="opPage = 1; loadOpLogs()">查询</el-button>
              <el-button size="small" @click="resetOpFilters">重置</el-button>
              <div class="grow" />
              <el-button size="small" :icon="Refresh" @click="loadOpLogs">刷新</el-button>
            </div>

            <el-table v-loading="opLoading" :data="opLogs" size="small" empty-text="暂无操作日志">
              <el-table-column label="时间" width="150">
                <template #default="{ row }"><span class="mono cell-time">{{ row.time }}</span></template>
              </el-table-column>
              <el-table-column prop="user" label="用户" width="96" show-overflow-tooltip />
              <el-table-column label="操作" width="88" align="center">
                <template #default="{ row }">
                  <span class="st-pill" :class="'st-pill--' + opTag(row.action)">{{ row.action }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="module" label="模块" width="92" show-overflow-tooltip />
              <el-table-column label="操作内容" min-width="260" show-overflow-tooltip>
                <template #default="{ row }">{{ row.detail || '—' }}</template>
              </el-table-column>
              <el-table-column label="接口" min-width="160" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="mono muted">{{ row.method }} {{ row.path }}</span>
                </template>
              </el-table-column>
              <el-table-column label="结果" width="72" align="center">
                <template #default="{ row }">
                  <span class="mono" :class="row.status_code >= 400 ? 'is-bad' : 'muted'">{{ row.status_code }}</span>
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="76" align="right">
                <template #default="{ row }"><span class="mono muted">{{ fmtDuration(row.duration_ms) }}</span></template>
              </el-table-column>
              <el-table-column prop="ip" label="来源" width="116" show-overflow-tooltip />
            </el-table>

            <el-pagination
              v-if="opTotal > 0"
              class="pager"
              size="small"
              layout="total, sizes, prev, pager, next"
              :total="opTotal"
              :current-page="opPage"
              :page-size="opPageSize"
              :page-sizes="[10, 20, 50]"
              @current-change="(p) => { opPage = p; loadOpLogs() }"
              @size-change="(s) => { opPageSize = s; opPage = 1; loadOpLogs() }"
            />
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 技能管理 ------------------------------ -->
        <el-tab-pane v-if="auth.isAdmin" :label="`技能管理${skills.length ? ' (' + skills.length + ')' : ''}`" name="skills">
          <div class="tab-body">
            <el-table v-loading="skillsLoading" :data="skills" size="default" empty-text="暂无技能">
              <el-table-column label="技能" min-width="200">
                <template #default="{ row }">
                  <div class="skill-cell">
                    <span class="skill-icon"><el-icon><Tools /></el-icon></span>
                    <span class="skill-name">{{ row.name }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="说明" min-width="280" show-overflow-tooltip />
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <span class="st-pill" :class="row.is_builtin || row.is_active ? 'st-pill--success' : 'st-pill--info'">
                    {{ row.is_builtin ? '内置' : row.is_active ? '启用' : '禁用' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" align="center">
                <template #default="{ row }">
                  <el-button v-if="!row.is_builtin" link type="danger" size="small" @click="deleteSkill(row.id)">删除</el-button>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 新闻采集 ------------------------------ -->
        <el-tab-pane v-if="auth.isAdmin" label="新闻采集" name="news">
          <div class="tab-body">
            <el-form label-width="112px" class="form-narrow">
              <div class="form-section">
                <div class="section-title">新闻来源</div>
                <el-form-item label="来源列表">
                  <el-input v-model="newsSources" type="textarea" :rows="4" class="mi" placeholder="每行一条，格式：名称|URL" />
                </el-form-item>
              </div>
              <div class="form-section">
                <div class="section-title">执行</div>
                <el-form-item label-width="0">
                  <el-button type="primary" :loading="newsSaving" @click="saveNews">保存新闻来源</el-button>
                  <el-button :loading="batchLoading" @click="batchCollect">批量采集客户新闻 + 联系人动态</el-button>
                </el-form-item>
              </div>
            </el-form>
            <div class="note-box">
              新闻采集的运行记录已并入「采集日志」标签页，可按任务类型「客户新闻 / 联系人动态」筛选。
              <button type="button" class="link-like" @click="filters.task_type = 'all'; tab = 'logs'">前往采集日志 →</button>
            </div>
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 账号管理 ------------------------------ -->
        <el-tab-pane v-if="auth.isAdmin" :label="`账号管理${users.length ? ' (' + users.length + ')' : ''}`" name="users">
          <div class="tab-body">
            <div class="ai-toolbar">
              <div class="note-box note-box--inline">
                每个同事一个账号，口令各自保管；停用或删除都只是打标记，账号行留在库里，历史操作痕迹仍可追溯。
              </div>
              <div class="ai-toolbar-actions">
                <el-button type="primary" :icon="Plus" @click="openUserForm()">添加账号</el-button>
              </div>
            </div>
            <el-table v-loading="usersLoading" :data="users" size="default" empty-text="暂无账号">
              <el-table-column label="账号" min-width="150">
                <template #default="{ row }">
                  <div class="skill-cell">
                    <el-avatar :size="26">{{ (row.display_name || row.username).slice(0, 1) }}</el-avatar>
                    <div>
                      <div class="skill-name">{{ row.display_name || row.username }}</div>
                      <div class="serial mono">{{ row.username }}</div>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="角色" width="110" align="center">
                <template #default="{ row }">
                  <span class="st-pill" :class="row.role === 'admin' ? 'st-pill--warning' : 'st-pill--info'">
                    {{ row.role === 'admin' ? '管理员' : '销售' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <span class="st-pill" :class="row.is_active ? 'st-pill--success' : 'st-pill--danger'">
                    {{ row.is_active ? '可用' : '已停用' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="最近登录" width="150">
                <template #default="{ row }">{{ row.last_login_at ? fmtDate(row.last_login_at) : '—' }}</template>
              </el-table-column>
              <el-table-column label="操作" width="230" align="center">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="openUserForm(row)">编辑</el-button>
                  <el-button link type="primary" size="small" @click="openPwdForm(row)">重置口令</el-button>
                  <el-button link type="danger" size="small" :disabled="row.id === auth.user.id" @click="deleteUser(row)">
                    {{ row.id === auth.user.id ? '本人' : '删除' }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 我的口令 ------------------------------ -->
        <el-tab-pane :label="auth.isAdmin ? '安全' : '我的口令'" name="security">
          <div class="tab-body">
            <el-form label-width="112px" class="form-narrow">
              <div class="form-section">
                <div class="section-title">我的登录口令</div>
                <el-form-item label="当前账号">
                  <span class="mono">{{ auth.user ? auth.user.username : '—' }}</span>
                  <span class="muted" style="margin-left: 8px">{{ auth.roleLabel }}</span>
                </el-form-item>
                <el-form-item label="当前口令">
                  <el-input v-model="pwd.old" type="password" show-password autocomplete="off" />
                </el-form-item>
                <el-form-item label="新口令">
                  <el-input v-model="pwd.next" type="password" show-password autocomplete="off" placeholder="至少 6 位" />
                </el-form-item>
                <el-form-item label="确认新口令">
                  <el-input v-model="pwd.confirm" type="password" show-password autocomplete="off" />
                </el-form-item>
                <el-form-item label-width="0">
                  <el-button type="primary" :loading="pwdSaving" @click="savePassword">修改口令</el-button>
                </el-form-item>
              </div>
            </el-form>
            <div class="note-box">
              只能修改自己账号的口令，改完只影响本账号，其他同事不受影响。
              口令只以散列形式存库，任何接口都不会回传原文；服务端对连续错误尝试有锁定保护。
              忘记口令时请管理员在「账号管理」里重置。
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 账号表单（新增/编辑） -->
    <el-dialog v-model="userFormVisible" :title="userEditId ? '编辑账号' : '添加账号'" width="460px" destroy-on-close>
      <el-form label-width="92px">
        <el-form-item label="账号名" required>
          <el-input v-model="uform.username" :disabled="!!userEditId" placeholder="登录用，如 zhangsan" class="mi" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="uform.display_name" placeholder="如 张三" />
        </el-form-item>
        <el-form-item v-if="!userEditId" label="初始口令" required>
          <el-input v-model="uform.password" type="password" show-password placeholder="至少 6 位，告知本人后可自行修改" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="uform.role" style="width: 160px">
            <el-option label="销售" value="sales" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="userEditId" label="启用">
          <el-switch v-model="uform.is_active" active-text="可登录" inactive-text="已停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userFormVisible = false">取消</el-button>
        <el-button type="primary" :loading="userSaving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <!-- 管理员重置他人口令 -->
    <el-dialog v-model="resetVisible" :title="`重置「${resetRow ? (resetRow.display_name || resetRow.username) : ''}」的口令`" width="420px" destroy-on-close>
      <el-form label-width="92px">
        <el-form-item label="新口令" required>
          <el-input v-model="resetValue" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
      </el-form>
      <div class="note-box note-box--inline">重置后对方原口令即刻失效，需要用新口令重新登录。</div>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetting" @click="saveReset">确定重置</el-button>
      </template>
    </el-dialog>

    <!-- 日志详情抽屉 -->
    <el-drawer v-model="drawer" title="采集日志详情" size="720px" direction="rtl">
      <div v-if="detail" class="drawer-body">
        <DetailGrid :items="drawerItems" dense>
          <template #status>
            <span class="st-pill" :class="'st-pill--' + statusTag(detail.status)">
              <i class="st-dot" />{{ statusLabel(detail.status) }}
            </span>
          </template>
          <template #counts>
            <span class="mono is-ok">{{ detail.items_count }}</span>
            <span class="drawer-sep">/</span>
            <span class="mono is-bad">{{ detail.error_count }}</span>
          </template>
        </DetailGrid>

        <div class="sub-head">报错分类汇总</div>
        <div v-if="detail.error_types && detail.error_types.length" class="chip-bar">
          <span v-for="t in detail.error_types" :key="t.code" class="st-pill" :class="'st-pill--' + sevTag(t.severity)">
            {{ t.label }} <b class="mono">{{ t.count }}</b>
          </span>
        </div>
        <div v-else class="muted">本次采集未产生异常。</div>

        <div class="sub-head">异常明细（{{ (detail.error_detail || []).length }}）</div>
        <el-table :data="detail.error_detail || []" size="small" border empty-text="无">
          <el-table-column label="报错类型" width="130">
            <template #default="{ row }">
              <span class="st-pill" :class="'st-pill--' + sevTag(row.severity)">{{ row.label }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="stage" label="阶段" width="100" />
          <el-table-column prop="target" label="对象" min-width="140" show-overflow-tooltip />
          <el-table-column prop="raw" label="原始报错" min-width="240" show-overflow-tooltip />
          <el-table-column prop="hint" label="处理建议" min-width="240" show-overflow-tooltip />
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Lightning, Tools, Document, Refresh, Search, Delete, Plus, Download } from '@element-plus/icons-vue'
import { get, getList, post, put, del, fmtDate, downloadCsv } from '../api'
import { useCrawlStore } from '../stores/app'
import { useAuthStore } from '../stores/auth'
import PageHeader from '../components/PageHeader.vue'
import DetailGrid from '../components/DetailGrid.vue'
import PageTable from '../components/PageTable.vue'

const crawl = useCrawlStore()
const auth = useAuthStore()
const tab = ref(auth.isAdmin ? 'ai' : 'security')

// ---- 账号管理（仅管理员） ----
const users = ref([])
const usersLoading = ref(false)
const userFormVisible = ref(false)
const userEditId = ref(null)
const userSaving = ref(false)
const uform = reactive({ username: '', display_name: '', password: '', role: 'sales', is_active: true })
const resetVisible = ref(false)
const resetRow = ref(null)
const resetValue = ref('')
const resetting = ref(false)

async function loadUsers() {
  usersLoading.value = true
  users.value = await getList('/users')
  usersLoading.value = false
}
function openUserForm(row) {
  userEditId.value = row ? row.id : null
  Object.assign(uform, {
    username: row ? row.username : '',
    display_name: row ? row.display_name || '' : '',
    password: '',
    role: row ? row.role : 'sales',
    is_active: row ? !!row.is_active : true,
  })
  userFormVisible.value = true
}
async function saveUser() {
  if (!uform.username.trim()) return ElMessage.warning('请填写账号名')
  if (!userEditId.value && uform.password.length < 6) return ElMessage.warning('初始口令至少 6 位')
  userSaving.value = true
  const r = userEditId.value
    ? await put(`/users/${userEditId.value}`, {
        display_name: uform.display_name, role: uform.role, is_active: uform.is_active })
    : await post('/users', {
        username: uform.username.trim(), password: uform.password,
        display_name: uform.display_name, role: uform.role })
  userSaving.value = false
  if (r.error) return ElMessage.error(r.error)
  userFormVisible.value = false
  ElMessage.success(userEditId.value ? '账号已更新' : '账号已创建')
  loadUsers()
}
function openPwdForm(row) {
  resetRow.value = row
  resetValue.value = ''
  resetVisible.value = true
}
async function saveReset() {
  if (resetValue.value.length < 6) return ElMessage.warning('新口令至少 6 位')
  resetting.value = true
  const r = await post(`/users/${resetRow.value.id}/password`, { password: resetValue.value })
  resetting.value = false
  if (r.error) return ElMessage.error(r.error)
  resetVisible.value = false
  ElMessage.success('口令已重置')
}
async function deleteUser(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除账号「${row.display_name || row.username}」？删除后该账号立即无法登录，历史操作记录仍保留。`,
      '删除账号', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/users/${row.id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('账号已删除')
  loadUsers()
}

// ---- 访问口令修改 ----
const pwd = reactive({ old: '', next: '', confirm: '' })
const pwdSaving = ref(false)
async function savePassword() {
  if (pwd.next.length < 6) return ElMessage.warning('新口令至少 6 位')
  if (pwd.next !== pwd.confirm) return ElMessage.warning('两次输入的新口令不一致')
  pwdSaving.value = true
  const err = await auth.change(pwd.old, pwd.next)
  pwdSaving.value = false
  if (err) return ElMessage.error(err)
  Object.assign(pwd, { old: '', next: '', confirm: '' })
  ElMessage.success('访问口令已更新')
}
const sched = ref({ crawl: { enabled: false, time: '08:00', next_run: '' }, backup: { schedule: '每日 02:30', next_run: '', keep: 14, list: [] } })
const backuping = ref(false)
const backupMsg = ref('')
async function loadSched() {
  const r = await get('/config/scheduler')
  if (r && !r.error) sched.value = r
}
async function backupNow() {
  backuping.value = true
  backupMsg.value = ''
  const r = await post('/config/backup-now')
  backuping.value = false
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(r.message || '备份完成')
  backupMsg.value = '已完成 ' + new Date().toLocaleTimeString('zh-CN', { hour12: false })
  loadSched()
}

const STATUS_LIST = [
  { value: 'running', label: '进行中', tag: 'info' },
  { value: 'success', label: '成功', tag: 'success' },
  { value: 'partial', label: '部分异常', tag: 'warning' },
  { value: 'failed', label: '失败', tag: 'danger' },
  { value: 'interrupted', label: '已中断', tag: 'info' },
]

const providers = ref([])
const aiSaving = ref(false)
const enabledCount = computed(() => providers.value.filter((p) => p.enabled).length)

// 添加 / 修改 弹窗
const providerFormVisible = ref(false)
const providerEditIndex = ref(null)
const pform = reactive({
  id: '', name: '', endpoint: '', model: '', api_key: '',
  has_key: false, key_masked: '', enabled: true, verifying: false, verify: null,
})
const maskLocal = (k) => '••••' + (k.length >= 4 ? k.slice(-4) : k)

const crawlForm = reactive({ sources: '', limit: 5, lastAt: '', kwFilter: true, keywords: '' })
const crawlFormRef = ref(null)
const crawlSaving = ref(false)
const crawlRules = {
  sources: [{ required: true, message: '请至少填写一条采集来源', trigger: 'blur' }],
}

const newsSources = ref('')
const newsSaving = ref(false)
const skills = ref([])
const skillsLoading = ref(false)
const batchLoading = ref(false)

// ------------------------------ 采集日志 ------------------------------
const logs = ref([])
const logsLoading = ref(false)
const logTotal = ref(0)
const page = ref(1)
const pageSize = ref(20)
const taskTypes = ref([])
const errorTypes = ref([])
const detail = ref(null)
const drawer = ref(false)
// 默认看全部时间：采集不是每天都有，默认收窄窗口会让页面看起来"没有日志"
const filters = reactive({ task_type: 'all', status: 'all', error_code: 'all', days: 'all', q: '' })
const logStats = reactive({ total: 0, items_total: 0, error_total: 0, by_status: {}, error_types: [] })

const logTabLabel = computed(() => (logStats.total ? `采集日志 (${logStats.total})` : '采集日志'))

const successRate = computed(() => {
  const st = logStats.by_status || {}
  const ok = (st.success || 0) + (st.partial || 0)
  const all = logStats.total || 0
  return all ? Math.round((ok / all) * 100) + '%' : '—'
})

// 报错类型字典按大类分组，供筛选下拉使用
const errorTypeGroups = computed(() => {
  const groups = {}
  for (const t of errorTypes.value) {
    (groups[t.category] = groups[t.category] || []).push(t)
  }
  return Object.entries(groups).map(([category, items]) => ({ category, items }))
})

const typeHint = (code) => errorTypes.value.find((t) => t.code === code)?.hint || ''

const statusLabel = (s) => STATUS_LIST.find((x) => x.value === s)?.label || s || '—'
const statusTag = (s) => STATUS_LIST.find((x) => x.value === s)?.tag || 'info'
const sevTag = (sev) => (sev === 'error' ? 'danger' : sev === 'warning' ? 'warning' : 'info')

const fmtTime = (d) => (d ? String(d).substring(0, 19) : '—')
const fmtDuration = (ms) => {
  const n = Number(ms) || 0
  if (!n) return '—'
  return n < 1000 ? `${n}ms` : `${(n / 1000).toFixed(1)}s`
}

// 详情抽屉的字段清单（DetailGrid 新 API：{label, value, full, mono, slot}）
const drawerItems = computed(() => {
  const d = detail.value || {}
  return [
    { label: '任务类型', value: d.task_type },
    { label: '状态', slot: 'status' },
    { label: '开始时间', value: fmtTime(d.started_at), mono: true },
    { label: '结束时间', value: fmtTime(d.finished_at), mono: true },
    { label: '耗时', value: fmtDuration(d.duration_ms), mono: true },
    { label: '新增 / 异常', slot: 'counts' },
    { label: '搜索范围', value: `${d.range_start || '—'} ~ ${d.range_end || '—'}`, full: true, mono: true },
    { label: '关键词', value: d.keywords, full: true },
    { label: '来源', value: d.sources, full: true },
    { label: '结果信息', value: d.message, full: true },
  ]
})

const parseSources = (v) => (v || '').split('\n').map((s) => s.trim()).filter(Boolean).map((l) => {
  const sep = l.indexOf('|')
  if (sep > 0) return { name: l.slice(0, sep).trim(), url: l.slice(sep + 1).trim(), enabled: true }
  return { name: l, url: l, enabled: true }
})
const sourcesToText = (cfg, key) => {
  let sources = []
  try { sources = JSON.parse(cfg[key]?.value || '[]') } catch (e) {}
  if (Array.isArray(sources) && sources.length) {
    return sources.filter((s) => s && s.url).map((s) => `${s.name || s.url}|${s.url}`).join('\n')
  }
  return ''
}

async function loadProviders() {
  const list = await getList('/config/ai-providers')
  providers.value = list.map((p) => ({
    id: p.id || '',
    name: p.name || '',
    endpoint: p.endpoint || '',
    model: p.model || '',
    api_key: '',                 // 空 = 不修改，沿用后端已存的 key
    has_key: !!p.has_key,
    key_masked: p.key_masked || '',
    enabled: p.enabled !== false,
    verifying: false,
    verify: null,
  }))
}

function openProviderForm(index = null) {
  providerEditIndex.value = index
  if (index === null) {
    Object.assign(pform, {
      id: '', name: '', endpoint: '', model: '', api_key: '',
      has_key: false, key_masked: '', enabled: true, verifying: false, verify: null,
    })
  } else {
    const p = providers.value[index]
    // 编辑：Key 输入框留空即"不改动"，沿用该行已存的 key
    Object.assign(pform, {
      id: p.id, name: p.name, endpoint: p.endpoint, model: p.model, api_key: '',
      has_key: p.has_key, key_masked: p.key_masked, enabled: p.enabled, verifying: false, verify: null,
    })
  }
  providerFormVisible.value = true
}

async function verifyPayload(obj) {
  return post('/config/verify-ai', {
    id: obj.id, name: obj.name, endpoint: obj.endpoint, model: obj.model, api_key: obj.api_key,
  })
}

async function verifyForm() {
  if (!pform.endpoint || !pform.model) return ElMessage.warning('请先填写 Endpoint 与模型名称')
  pform.verifying = true
  pform.verify = null
  try {
    const r = await verifyPayload(pform)
    if (r.ok) {
      pform.verify = { ok: true }
      ElMessage.success(r.message || '连接正常')
    } else {
      pform.verify = { ok: false, label: r.label, hint: r.hint, error: r.error }
      ElMessage.error(r.label ? `${r.label}：${r.hint || r.error}` : (r.error || '连接失败'))
    }
  } finally {
    pform.verifying = false
  }
}

async function commitProviderForm() {
  if (!pform.endpoint || !pform.model) return ElMessage.warning('Endpoint 与模型名称为必填')
  const typed = pform.api_key && !pform.api_key.startsWith('••••') ? pform.api_key : ''
  if (providerEditIndex.value === null && !typed) return ElMessage.warning('请填写 API Key')
  if (providerEditIndex.value === null) {
    providers.value.push({
      id: pform.id, name: pform.name, endpoint: pform.endpoint, model: pform.model,
      api_key: typed, has_key: !!typed, key_masked: typed ? maskLocal(typed) : '',
      enabled: pform.enabled, verifying: false, verify: null,
    })
  } else {
    const p = providers.value[providerEditIndex.value]
    p.name = pform.name
    p.endpoint = pform.endpoint
    p.model = pform.model
    p.enabled = pform.enabled
    if (typed) { p.api_key = typed; p.has_key = true; p.key_masked = maskLocal(typed) }
    // 未填新 key：保留该行原有的 api_key / has_key / key_masked 不变
  }
  providerFormVisible.value = false
  // 立即自动落库：添加/修改即保存，避免"只点了弹窗确定、忘点外层保存配置"导致刷新丢失
  await saveProviders()
}

async function verifyRow(index) {
  const p = providers.value[index]
  if (!p.endpoint || !p.model) return ElMessage.warning('该行 Endpoint 或模型名称缺失')
  p.verifying = true
  try {
    const r = await verifyPayload(p)
    const label = p.name || p.model
    if (r.ok) ElMessage.success(`[${label}] ` + (r.message || '连接正常'))
    else ElMessage.error(r.label ? `[${label}] ${r.label}：${r.hint || r.error}` : (r.error || '连接失败'))
  } finally {
    p.verifying = false
  }
}

function removeProvider(i) {
  const p = providers.value[i]
  const label = p.name || p.model || '该服务'
  ElMessageBox.confirm(`确认删除模型服务「${label}」？删除后立即生效。`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  }).then(async () => {
    providers.value.splice(i, 1)
    await saveProviders()
  }).catch(() => {})
}

async function saveProviders() {
  for (const [idx, p] of providers.value.entries()) {
    if (!p.endpoint || !p.model) {
      return ElMessage.warning(`第 ${idx + 1} 家：Endpoint 与模型名称为必填`)
    }
    if (!p.has_key && !p.api_key) {
      return ElMessage.warning(`第 ${idx + 1} 家：请填写 API Key`)
    }
  }
  aiSaving.value = true
  try {
    const body = providers.value.map((p) => ({
      id: p.id, name: p.name, endpoint: p.endpoint, model: p.model,
      api_key: p.api_key, enabled: p.enabled,
    }))
    const r = await put('/config/ai-providers', body)
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(r.message || 'AI 配置已保存')
    await loadProviders()  // 重新拉取脱敏展示
  } finally {
    aiSaving.value = false
  }
}

async function saveCrawl() {
  if (!crawlFormRef.value) return
  const valid = await crawlFormRef.value.validate().catch(() => false)
  if (!valid) return
  crawlSaving.value = true
  try {
    const r = await put('/config', {
      keywords: crawlForm.keywords,
      crawl_sources: JSON.stringify(parseSources(crawlForm.sources)),
      crawl_limit: String(crawlForm.limit || 5),
      crawl_keyword_filter: crawlForm.kwFilter ? '1' : '0',
    })
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success('采集配置已保存')
  } finally {
    crawlSaving.value = false
  }
}

async function doCrawl() {
  const msg = await crawl.start()
  msg ? ElMessage.error(msg) : ElMessage.info('采集已启动，正在抓取并 AI 分析...')
}

async function saveNews() {
  newsSaving.value = true
  try {
    const r = await put('/config', { news_sources: JSON.stringify(parseSources(newsSources.value)) })
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success('新闻来源已保存')
  } finally {
    newsSaving.value = false
  }
}

async function batchCollect() {
  batchLoading.value = true
  try {
    const r = await post('/news/collect-all', { type: 'all' })
    if (r.error) { ElMessage.error(r.error); return }
    const suffix = r.errors?.length ? `（${r.errors.length} 个异常）` : ''
    ElMessage.success((r.message || '采集完成') + suffix)
    loadLogs()
  } finally {
    batchLoading.value = false
  }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const qs = new URLSearchParams({
      page: String(page.value), page_size: String(pageSize.value),
      task_type: filters.task_type, status: filters.status,
      error_code: filters.error_code, days: filters.days,
    })
    if (filters.q) qs.set('q', filters.q)
    const r = await get('/crawl/logs?' + qs.toString())
    if (r.error) { ElMessage.error(r.error); return }
    logs.value = r.items || []
    logTotal.value = r.total || 0
    taskTypes.value = r.task_types || []
    Object.assign(logStats, r.stats || {})
  } finally {
    logsLoading.value = false
  }
}

async function loadErrorTypes() {
  errorTypes.value = await getList('/error-types')
}

function resetFilters() {
  Object.assign(filters, { task_type: 'all', status: 'all', error_code: 'all', days: 'all', q: '' })
  page.value = 1
  loadLogs()
}

// 展开行时才拉取明细，避免列表接口返回大字段
async function onExpand(row, expanded) {
  const isOpen = Array.isArray(expanded) ? expanded.some((r) => r.id === row.id) : !!expanded
  if (!isOpen || row._detail) return
  const r = await get(`/crawl/logs/${row.id}`)
  row._detail = r.error_detail || []
}

async function openDetail(row) {
  const r = await get(`/crawl/logs/${row.id}`)
  if (r.error) return ElMessage.error(r.error)
  detail.value = r
  drawer.value = true
}

async function clearLogs() {
  const hasFilter = ['task_type', 'status', 'error_code', 'days'].some((k) => filters[k] && filters[k] !== 'all') || !!filters.q
  if (!hasFilter) return ElMessage.warning('请先设置筛选条件（任务 / 状态 / 报错类型 / 时间 / 关键词），只会清理筛选命中的日志')
  const qs = new URLSearchParams({
    task_type: filters.task_type, status: filters.status,
    error_code: filters.error_code, days: filters.days,
  })
  if (filters.q) qs.set('q', filters.q)
  try {
    await ElMessageBox.confirm(
      '仅清理当前筛选条件命中的采集日志（不影响已采集的线索/客户数据）。是否继续？',
      '清理采集日志', { type: 'warning', confirmButtonText: '清理选中', cancelButtonText: '取消' },
    )
  } catch (e) { return }
  const r = await del('/crawl/logs?' + qs.toString())
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(r.message || '已清理')
  page.value = 1
  loadLogs()
}

// ---- 操作日志（仅管理员） ----
const SUMMARY_ACTIONS = ['登录', '查询', '点击', '新增', '修改', '删除', '采集']
const OP_ACTION_TAG = {
  新增: 'success', 登录: 'success', 转化: 'success', 采集: 'success', 执行: 'success',
  修改: 'warning', 领取: 'warning', 批量操作: 'warning', 改密: 'warning', 恢复: 'warning',
  删除: 'danger', 初始化: 'danger',
  查询: 'info', 点击: 'info', 登出: 'info', 导出: 'info', 备份: 'info',
}
const opLogs = ref([])
const opTotal = ref(0)
const opPage = ref(1)
const opPageSize = ref(50)
const opLoading = ref(false)
const opStats = reactive({ by_action: {}, failures: 0, active_users: 0, scoped: 0 })
const opEnums = reactive({ users: [], actions: [], modules: [] })
const opFilters = reactive({ days: 'today', user: 'all', action: 'all', module: 'all', result: 'all', q: '' })
// 从每日总结「查看这一天明细」带过来的精确日期区间；为空时按 opFilters.days 走
const dayRange = ref({ start: '', end: '' })
const sumRows = ref([])
const sumDays = ref(30)
const sumPage = ref(1)
const sumPageSize = ref(20)
const sumLoading = ref(false)
const sumGenerating = ref(false)
let opLoaded = false

const opTag = (a) => OP_ACTION_TAG[a] || 'info';
const opChipTag = (a) => ({ success: 'success', warning: 'warning', danger: 'danger' }[opTag(a)] || 'info');
const opTabLabel = computed(() => `操作日志${opTotal.value ? ` (${opTotal.value})` : ''}`);
const opStatActions = computed(() =>
  Object.entries(opStats.by_action || {}).map(([code, count]) => ({ code, count })));

function localDay(offset = 0) {
  const d = new Date()
  d.setDate(d.getDate() - offset)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
// 今日/近 7 天口径直接来自每日总结，不再单独发一次统计请求
const todayRow = computed(() => sumRows.value.find((r) => r.day === localDay()) || { total: 0, by_action: {}, failures: 0 })
const todayWrites = computed(() => SUMMARY_ACTIONS.filter((a) => ['新增', '修改', '删除'].includes(a))
  .reduce((n, a) => n + (todayRow.value.by_action?.[a] || 0), 0))
const weekRows = computed(() => sumRows.value.filter((r) => r.day >= localDay(6)))
const weekTotal = computed(() => weekRows.value.reduce((n, r) => n + (r.total || 0), 0))
const weekFails = computed(() => weekRows.value.reduce((n, r) => n + (r.failures || 0), 0))
const sumPageRows = computed(() => {
  const start = (sumPage.value - 1) * sumPageSize.value
  return sumRows.value.slice(start, start + sumPageSize.value)
})

function opQuery(extra = {}) {
  const qs = new URLSearchParams({
    days: opFilters.days, user: opFilters.user, action: opFilters.action,
    module: opFilters.module, result: opFilters.result,
  })
  if (opFilters.q) qs.set('q', opFilters.q)
  if (dayRange.value.start) {
    qs.set('start', dayRange.value.start)
    qs.set('end', dayRange.value.end || dayRange.value.start)
    qs.delete('days')
  }
  Object.entries(extra || {}).forEach(([k, v]) => qs.set(k, String(v)))
  return qs.toString()
}

async function loadOpLogs() {
  opLoading.value = true
  try {
    const r = await get(`/audit/logs?${opQuery({ page: opPage.value, page_size: opPageSize.value })}`)
    if (r.error) { ElMessage.error(r.error); return }
    opLogs.value = r.items || []
    opTotal.value = r.total || 0
    Object.assign(opStats, r.stats || {})
    Object.assign(opEnums, { users: r.users || [], actions: r.actions || [], modules: r.modules || [] })
  } finally {
    opLoading.value = false
  }
}

async function loadSummary() {
  sumLoading.value = true
  try {
    const r = await get(`/audit/summary?days=${sumDays.value}`)
    if (r.error) { ElMessage.error(r.error); return }
    // 最近的日期排在最前，和明细列表保持同一个阅读方向
    sumRows.value = (r.days || []).slice().reverse()
    const maxPage = Math.max(1, Math.ceil(sumRows.value.length / sumPageSize.value))
    if (sumPage.value > maxPage) sumPage.value = maxPage
  } finally {
    sumLoading.value = false
  }
}

async function generateSummary(day) {
  sumGenerating.value = true
  try {
    const r = await post('/audit/summary', { day: day || localDay() })
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(r.message || '已生成')
    await Promise.all([loadSummary(), loadOpLogs()])
  } finally {
    sumGenerating.value = false
  }
}

function openDayLogs(day) {
  Object.assign(opFilters, { days: 'all', user: 'all', action: 'all', module: 'all', result: 'all', q: '' })
  dayRange.value = { start: day, end: day }
  opPage.value = 1
  loadOpLogs()
}

// 手动改时间范围就等于放弃「某一天」的精确区间
function onOpDaysChange() {
  dayRange.value = { start: '', end: '' }
  opPage.value = 1
  loadOpLogs()
}

function resetOpFilters() {
  Object.assign(opFilters, { days: 'today', user: 'all', action: 'all', module: 'all', result: 'all', q: '' })
  dayRange.value = { start: '', end: '' }
  opPage.value = 1
  loadOpLogs()
}

async function exportOpLogs() {
  const msg = await downloadCsv(`/audit/export?${opQuery()}`, `操作日志_${localDay()}.csv`)
  if (msg) ElMessage.error(msg)
}

async function loadSkills() {
  skillsLoading.value = true
  const data = await get('/skills')
  skills.value = [
    ...((data.builtin || []).map((s) => ({ ...s, is_builtin: true }))),
    ...(data.custom || []),
  ]
  skillsLoading.value = false
}

async function deleteSkill(id) {
  try {
    await ElMessageBox.confirm('确认删除该技能？', '删除技能', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/skills/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除')
  loadSkills()
}

onMounted(async () => {
  if (auth.isAdmin) loadUsers()
  if (!auth.isAdmin) return   // 销售只用到「我的口令」，其余配置接口一律 403
  loadSched()
  const config = await get('/config')
  const getV = (k, d = '') => config[k]?.value || d
  loadProviders()
  crawlForm.sources = sourcesToText(config, 'crawl_sources')
  crawlForm.lastAt = config.last_crawl_at?.value || '首次采集（自动回溯最近 7 天）'
  crawlForm.limit = Number(config.crawl_limit?.value || 5) || 5
  crawlForm.kwFilter = (config.crawl_keyword_filter?.value || '1') !== '0'
  crawlForm.keywords = getV('keywords', '无人机,林业,病虫害,巡检')
  newsSources.value = sourcesToText(config, 'news_sources')
  await nextTick()
  crawlFormRef.value?.clearValidate()
  loadSkills()
  loadErrorTypes()
  loadLogs()
  crawl.checkRunning()
})

// 采集结束后自动刷新日志
watch(() => crawl.finishedAt, () => {
  if (crawl.finishedAt) { page.value = 1; loadLogs() }
})

// 操作日志只在进入标签时拉：日志表会长年累月地涨，不该在打开设置页时就查两次
watch(tab, (t) => {
  if (t !== 'oplog' || opLoaded) return
  opLoaded = true
  loadSummary()
  loadOpLogs()
})
</script>

<style scoped>
.settings-card {
  background: var(--el-bg-color);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  box-shadow: var(--crm-shadow-xs);
  padding: 2px 22px 22px;
}
.settings-card :deep(.el-tabs__header) { margin-bottom: 16px; }

.tab-body { padding: 2px 0 0; }
.form-section { padding-bottom: 4px; }
.form-narrow { max-width: 640px; }
.w-full { width: 100%; }

/* 代码/URL 输入用等宽字，与全局 .mono 区分：这里穿透到 Element 内部 input */
.mi :deep(.el-input__inner),
.mi :deep(.el-textarea__inner) { font-family: var(--crm-font-mono); font-size: 12.5px; }

.note-box {
  max-width: 700px;
  margin-top: 6px;
  background: var(--crm-slate-25);
  border: 1px solid var(--crm-border-hairline);
  border-radius: var(--crm-radius-md);
  padding: 10px 14px;
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--crm-fg-3);
}
.link-like {
  border: none; background: none; padding: 0 2px; cursor: pointer;
  font-size: 12.5px; color: var(--crm-pine-600); font-weight: 500;
}
.link-like:hover { text-decoration: underline; }

/* 多家 AI 配置（标准列表） */
.ai-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.ai-toolbar .note-box--inline { margin: 0; max-width: 620px; }
.ai-toolbar-actions { display: flex; gap: 8px; flex-shrink: 0; }
.table-wrap { border: 1px solid var(--crm-border-soft); border-radius: var(--crm-radius-lg); overflow: hidden; }
.row-actions { display: inline-flex; align-items: center; gap: 4px; justify-content: flex-end; }
.serial { font-size: 12.5px; color: var(--crm-fg-3); }
.dim { color: var(--crm-fg-3); }
.is-bad { color: var(--crm-rose-500); }
.ai-count { margin-top: 10px; font-size: 12.5px; }
.verify-cell { display: flex; align-items: center; gap: 10px; min-height: 24px; }
.verify-result { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; }
.verify-result.is-ok { color: var(--crm-pine-600); }
.verify-result.is-bad { color: var(--crm-rose-500); }
.verify-err {
  margin: 0 0 4px 104px; font-size: 12.5px; line-height: 1.6;
  color: var(--crm-rose-500);
  background: var(--crm-rose-50);
  border: 1px solid var(--crm-border-hairline);
  border-radius: var(--crm-radius-sm);
  padding: 6px 10px;
}

/* 采集运行状态 */
.run-state {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  max-width: 700px; margin-top: 4px;
  background: var(--crm-sky-50);
  border: 1px solid var(--crm-border-hairline);
  border-radius: var(--crm-radius-md);
  padding: 10px 14px; font-size: 13px; color: var(--crm-fg-2); line-height: 1.7;
}
.run-state--ok { background: var(--crm-pine-25); }
.run-pulse {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--crm-sky-500); position: relative; flex-shrink: 0;
}
.run-pulse::after {
  content: ''; position: absolute; inset: -4px; border-radius: 50%;
  border: 1px solid var(--crm-sky-500); opacity: .5;
  animation: run-ping 1.4s var(--crm-ease-out) infinite;
}
@keyframes run-ping {
  0% { transform: scale(.6); opacity: .6; }
  100% { transform: scale(1.5); opacity: 0; }
}
.run-errors { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.run-errors-title { font-size: 12.5px; color: var(--crm-fg-3); margin-right: 4px; }
.err-chip { max-width: 100%; }

/* 概览小卡 */
.mini-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.mini-card {
  background: var(--crm-slate-25);
  border: 1px solid var(--crm-border-hairline);
  border-radius: var(--crm-radius-md);
  padding: 11px 14px;
}
.mini-label { font-size: 12px; color: var(--crm-fg-3); }
.mini-value { font-size: 21px; font-weight: 650; margin-top: 3px; color: var(--crm-fg-1); letter-spacing: -0.02em; }
.mini-value.is-ok { color: var(--crm-pine-600); }
.mini-value.is-bad { color: var(--crm-rose-500); }

/* 可点击过滤 chip */
.chip-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.bar-label { font-size: 12.5px; color: var(--crm-fg-3); margin-right: 2px; }
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  height: 25px; padding: 0 10px; border-radius: var(--crm-radius-full);
  border: 1px solid var(--crm-border-hairline);
  background: transparent; color: var(--crm-fg-2);
  font-size: 12px; line-height: 1; cursor: pointer;
  transition: border-color var(--crm-dur-fast) var(--crm-ease-out),
              background var(--crm-dur-fast) var(--crm-ease-out),
              color var(--crm-dur-fast) var(--crm-ease-out);
}
.chip:hover { border-color: var(--crm-pine-300); color: var(--crm-fg-1); }
.chip-n { font-family: var(--crm-font-mono); font-size: 11px; color: var(--crm-fg-4); font-style: normal; }
.chip.active { border-color: currentColor; font-weight: 500; }
.chip.active .chip-n { color: inherit; }
.chip--info.active { color: var(--crm-fg-2); background: var(--crm-slate-100); }
.chip--success.active { color: var(--crm-pine-600); background: var(--crm-pine-25); }
.chip--warning.active { color: var(--crm-amber-500); background: var(--crm-amber-50); }
.chip--danger.active { color: var(--crm-rose-500); background: var(--crm-rose-50); }

/* 日志筛选行 */
.log-filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 6px 0 12px; }
.f-select { width: 128px; }
.f-select.wide { width: 168px; }
.f-search { width: 220px; }
.grow { flex: 1; }

/* 状态 / 报错语义胶囊 */
.st-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 1px 8px; border-radius: var(--crm-radius-full);
  font-size: 12px; line-height: 18px; white-space: nowrap;
}
.st-pill--info { color: var(--crm-fg-2); background: var(--crm-slate-100); }
.st-pill--success { color: var(--crm-pine-600); background: var(--crm-pine-25); }
.st-pill--warning { color: var(--crm-amber-500); background: var(--crm-amber-50); }
.st-pill--danger { color: var(--crm-rose-500); background: var(--crm-rose-50); }
.st-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
.sv-inline { margin-right: 4px; }

.cell-time { font-size: 12.5px; }
.is-ok { color: var(--crm-pine-600); }
.is-bad { color: var(--crm-rose-500); }

/* 展开明细 / 抽屉 */
.detail-wrap { padding: 8px 12px 12px; }
.sub-head { font-size: 13px; font-weight: 650; color: var(--crm-fg-1); margin: 18px 0 8px; }
/* 操作日志：标题行要能挂筛选器与按钮，所以自己拉成 flex（全局 .section-title 是块级） */
.oplog-title { display: flex; align-items: center; gap: 8px; }
.summary-text { color: var(--crm-fg-2); }
.op-actions-row { margin-top: 8px; }
.detail-table { margin-bottom: 4px; }
.pager { margin-top: 12px; justify-content: flex-end; }
.drawer-body { padding-bottom: 20px; }
.drawer-sep { margin: 0 6px; color: var(--crm-fg-4); }

/* 技能单元格 */
.skill-cell { display: flex; align-items: center; gap: 9px; }
.skill-icon {
  width: 26px; height: 26px; border-radius: var(--crm-radius-sm);
  background: var(--crm-pine-25); color: var(--crm-pine-600);
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.skill-name { font-weight: 550; color: var(--crm-fg-1); }

.muted { color: var(--crm-fg-3); font-size: 12.5px; }

@media (max-width: 720px) {
  .mini-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .settings-card { padding: 2px 14px 16px; }
}
</style>

<style scoped>
.sched-card { background: var(--crm-slate-25, #fbfcfd); border: 1px solid var(--crm-border-soft, #e1e6ec); border-radius: 10px; padding: 14px 16px; }
.sched-item { padding: 4px 0; }
.sched-line { display: flex; align-items: center; gap: 8px; }
.sched-name { font-weight: 600; font-size: 13.5px; }
.sched-meta { margin-top: 4px; font-size: 12.5px; }
.backup-list { margin-top: 10px; border-top: 1px solid var(--crm-border-soft, #e1e6ec); padding-top: 8px; }
.backup-row { display: flex; justify-content: space-between; font-size: 12px; padding: 3px 0; }
</style>
