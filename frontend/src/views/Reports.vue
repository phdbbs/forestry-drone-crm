<template>
  <div class="page">
    <PageHeader title="数据报表" subtitle="线索趋势、商机漏斗与转化效率">
      <template #actions>
        <el-button :icon="Refresh" plain :loading="loading" @click="load">刷新数据</el-button>
      </template>
    </PageHeader>

    <el-row :gutter="14" class="stat-row">
      <el-col v-for="s in statCards" :key="s.label" :xs="12" :sm="12" :md="6">
        <StatCard v-bind="s" :loading="loading" />
      </el-col>
    </el-row>

    <div v-loading="loading" class="chart-grid">
      <div class="panel">
        <div class="panel-head">
          <span class="ph-icon"><el-icon :size="14"><TrendCharts /></el-icon></span>
          <span class="ph-title">线索月度趋势</span>
          <span class="ph-sub">新增 / 转化</span>
        </div>
        <div ref="monthlyRef" class="chart-box"></div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ph-icon"><el-icon :size="14"><Histogram /></el-icon></span>
          <span class="ph-title">商机漏斗</span>
          <span class="ph-sub">按金额（万）</span>
        </div>
        <div ref="funnelRef" class="chart-box"></div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ph-icon"><el-icon :size="14"><PieChart /></el-icon></span>
          <span class="ph-title">赢单 / 丢单分布</span>
        </div>
        <div ref="winLossRef" class="chart-box"></div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ph-icon"><el-icon :size="14"><DataAnalysis /></el-icon></span>
          <span class="ph-title">阶段分布</span>
          <span class="ph-sub">按商机数</span>
        </div>
        <div ref="stagesRef" class="chart-box"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { Refresh, TrendCharts, Histogram, PieChart, DataAnalysis } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import StatCard from '../components/StatCard.vue'
import { get } from '../api'

const data = ref({})
const loading = ref(true)
const monthlyRef = ref(null)
const funnelRef = ref(null)
const winLossRef = ref(null)
const stagesRef = ref(null)
let charts = []

const statCards = computed(() => {
  const s = data.value.summary || {}
  return [
    { label: '总线索数', value: s.total_leads ?? 0, icon: 'Aim', tone: 'primary' },
    { label: '商机总数', value: s.total_opportunities ?? 0, icon: 'DataAnalysis', tone: 'info' },
    { label: '商机总金额', value: s.total_amount ?? 0, suffix: '万', precision: 2, icon: 'Coin', tone: 'warning' },
    { label: '转化率', value: s.conversion_rate ?? 0, suffix: '%', precision: 1, icon: 'TrendCharts', tone: 'success' },
  ]
})

// 主题色取自 CSS 变量，图表与页面主题保持一致
function themeColors() {
  const css = getComputedStyle(document.documentElement)
  const v = (n, fallback) => (css.getPropertyValue(n).trim() || fallback)
  return {
    primary: v('--crm-primary', '#136a47'),
    primarySoft: v('--crm-pine-300', '#4f9f76'),
    success: v('--crm-pine-500', '#136a47'),
    warning: v('--crm-amber-500', '#b45309'),
    danger: v('--crm-rose-500', '#b91c1c'),
    info: v('--crm-slate-400', '#7e8b9b'),
    sky: v('--crm-sky-500', '#0369a1'),
    fg2: v('--crm-fg-2', '#33414f'),
    fg3: v('--crm-fg-3', '#5c6b7c'),
    hairline: v('--crm-slate-100', '#eef1f4'),
    font: css.getPropertyValue('--crm-font-sans').trim() || 'Manrope, sans-serif',
    mono: css.getPropertyValue('--crm-font-mono').trim() || 'JetBrains Mono, monospace',
  }
}

function baseAxis(c) {
  return {
    axisLine: { lineStyle: { color: c.hairline } },
    axisTick: { show: false },
    axisLabel: { color: c.fg3, fontSize: 11, fontFamily: c.mono },
    splitLine: { lineStyle: { color: c.hairline, type: 'solid' } },
  }
}
function baseTooltip(c) {
  return {
    backgroundColor: 'rgba(255,255,255,0.96)',
    borderColor: c.hairline,
    borderWidth: 1,
    textStyle: { color: c.fg2, fontSize: 12, fontFamily: c.font },
    extraCssText: 'box-shadow:0 4px 16px rgba(15,23,42,.08);border-radius:8px;',
  }
}

function render() {
  const d = data.value
  const c = themeColors()
  const mk = (elRef, option) => {
    if (!elRef.value) return
    const chart = echarts.init(elRef.value)
    chart.setOption(option)
    charts.push(chart)
  }

  // 月度趋势：双 smooth 面积线
  mk(monthlyRef, {
    color: [c.primary, c.warning],
    tooltip: { ...baseTooltip(c), trigger: 'axis' },
    legend: { bottom: 0, itemWidth: 12, itemHeight: 2, textStyle: { color: c.fg3, fontSize: 11 } },
    grid: { left: 44, right: 20, top: 20, bottom: 50 },
    xAxis: { type: 'category', boundaryGap: false, data: (d.monthly_leads || []).map((m) => m.month), ...baseAxis(c), splitLine: { show: false } },
    yAxis: { type: 'value', minInterval: 1, ...baseAxis(c) },
    series: [
      {
        name: '新增线索', type: 'line', smooth: true, symbol: 'circle', symbolSize: 5,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(19,106,71,0.16)' },
            { offset: 1, color: 'rgba(19,106,71,0)' },
          ]),
        },
        lineStyle: { width: 2 },
        data: (d.monthly_leads || []).map((m) => m.leads),
      },
      {
        name: '已转化', type: 'line', smooth: true, symbol: 'circle', symbolSize: 5,
        areaStyle: { opacity: 0.06 },
        lineStyle: { width: 2 },
        data: (d.monthly_leads || []).map((m) => m.converted),
      },
    ],
  })

  // 漏斗：横向渐变柱
  const funnel = d.funnel || []
  mk(funnelRef, {
    tooltip: { ...baseTooltip(c), trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 96, right: 44, top: 10, bottom: 24 },
    xAxis: { type: 'value', ...baseAxis(c), axisLabel: { ...baseAxis(c).axisLabel, formatter: (v) => v >= 10000 ? (v / 10000) + 'w' : v } },
    yAxis: { type: 'category', data: funnel.map((f) => f.stage).reverse(), ...baseAxis(c), splitLine: { show: false }, axisLabel: { color: c.fg2, fontSize: 12, fontFamily: c.font } },
    series: [{
      type: 'bar',
      data: funnel.map((f) => f.amount).reverse(),
      barMaxWidth: 20,
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: c.primarySoft },
          { offset: 1, color: c.primary },
        ]),
      },
      label: { show: true, position: 'right', color: c.fg3, fontSize: 11, fontFamily: c.mono },
    }],
  })

  // 赢单 / 丢单：中心留白环形
  const wl = d.win_loss || []
  const wlTotal = wl.reduce((a, w) => a + (w.value || 0), 0)
  mk(winLossRef, {
    tooltip: { ...baseTooltip(c), trigger: 'item' },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: c.fg3, fontSize: 11 } },
    graphic: {
      type: 'text', left: 'center', top: '38%',
      style: {
        text: String(wlTotal), fill: c.fg2,
        font: `700 22px ${c.mono}`,
      },
    },
    series: [{
      type: 'pie', radius: ['58%', '78%'], center: ['50%', '44%'],
      itemStyle: { borderWidth: 2, borderColor: '#fff', borderRadius: 4 },
      label: { show: false },
      emphasis: { label: { show: false } },
      data: wl.map((w, i) => ({
        name: w.name,
        value: w.value,
        itemStyle: { color: [c.success, c.sky, c.danger][i % 3] },
      })),
    }],
  })

  // 阶段分布：圆角柱
  mk(stagesRef, {
    tooltip: { ...baseTooltip(c), trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 44, right: 20, top: 20, bottom: 46 },
    xAxis: { type: 'category', data: funnel.map((f) => f.stage), ...baseAxis(c), splitLine: { show: false }, axisLabel: { interval: 0, rotate: 20, color: c.fg3, fontSize: 11, fontFamily: c.font } },
    yAxis: { type: 'value', minInterval: 1, ...baseAxis(c) },
    series: [{
      type: 'bar', data: funnel.map((f) => f.count),
      barMaxWidth: 36,
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: c.primary },
          { offset: 1, color: c.primarySoft },
        ]),
      },
    }],
  })
}

function onResize() { charts.forEach((ch) => ch.resize()) }

async function load() {
  loading.value = true
  data.value = await get('/analytics')
  loading.value = false
  await nextTick()
  charts.forEach((ch) => ch.dispose())
  charts = []
  render()
}

onMounted(async () => {
  await load()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  charts.forEach((ch) => ch.dispose())
  charts = []
})
</script>

<style scoped>
.stat-row { margin-bottom: 14px; }
.stat-row :deep(.el-col) { margin-bottom: 14px; }

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
@media (max-width: 1000px) { .chart-grid { grid-template-columns: 1fr; } }

.panel {
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  box-shadow: var(--crm-shadow-xs);
}
.panel-head {
  display: flex; align-items: center; gap: 8px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--crm-border-soft);
}
.ph-icon {
  width: 22px; height: 22px; border-radius: 6px;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--crm-pine-25); color: var(--crm-pine-600);
  flex-shrink: 0;
}
.ph-title { font-size: 13px; font-weight: 600; color: var(--crm-fg-1); letter-spacing: -0.005em; }
.ph-sub { font-size: 11.5px; color: var(--crm-fg-4); margin-left: auto; }

.chart-box { height: 280px; padding: 10px 8px 4px; }
</style>
