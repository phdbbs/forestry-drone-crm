<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">数据报表</h2>
      <div class="page-toolbar">
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新数据</el-button>
      </div>
    </div>

    <el-row :gutter="16" class="card-block">
      <el-col v-for="s in statCards" :key="s.label" :xs="12" :sm="12" :md="6">
        <StatCard v-bind="s" :loading="loading" />
      </el-col>
    </el-row>

    <div v-loading="loading" class="chart-grid">
      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <el-icon class="head-icon"><TrendCharts /></el-icon>
            <span>线索月度趋势</span>
          </div>
        </template>
        <div ref="monthlyRef" class="chart-box"></div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <el-icon class="head-icon"><Histogram /></el-icon>
            <span>商机漏斗（金额）</span>
          </div>
        </template>
        <div ref="funnelRef" class="chart-box"></div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <el-icon class="head-icon"><PieChart /></el-icon>
            <span>赢单 / 丢单分布</span>
          </div>
        </template>
        <div ref="winLossRef" class="chart-box"></div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <el-icon class="head-icon"><DataAnalysis /></el-icon>
            <span>阶段分布（商机数）</span>
          </div>
        </template>
        <div ref="stagesRef" class="chart-box"></div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { Refresh, TrendCharts, Histogram, PieChart, DataAnalysis } from '@element-plus/icons-vue'
import StatCard from '../components/StatCard.vue'
import { get, fmtNum } from '../api'

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
    primary: v('--crm-primary', '#2f7d4f'),
    success: v('--el-color-success', '#67c23a'),
    warning: v('--el-color-warning', '#e6a23c'),
    danger: v('--el-color-danger', '#f56c6c'),
    info: v('--el-color-info', '#909399'),
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

  // 月度趋势
  mk(monthlyRef, {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { left: 44, right: 20, top: 20, bottom: 50 },
    xAxis: { type: 'category', data: (d.monthly_leads || []).map((m) => m.month) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '新增线索', type: 'line', smooth: true, areaStyle: { opacity: .1 },
        data: (d.monthly_leads || []).map((m) => m.leads), itemStyle: { color: c.primary },
      },
      {
        name: '已转化', type: 'line', smooth: true, areaStyle: { opacity: .1 },
        data: (d.monthly_leads || []).map((m) => m.converted), itemStyle: { color: c.warning },
      },
    ],
  })

  // 漏斗（横向柱）
  const funnel = d.funnel || []
  mk(funnelRef, {
    tooltip: { trigger: 'axis' },
    grid: { left: 90, right: 30, top: 10, bottom: 20 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: funnel.map((f) => f.stage).reverse() },
    series: [{
      type: 'bar',
      data: funnel.map((f) => f.amount).reverse(),
      itemStyle: { color: c.primary },
      barMaxWidth: 24,
    }],
  })

  // 赢单 / 丢单
  mk(winLossRef, {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie', radius: ['40%', '65%'],
      data: (d.win_loss || []).map((w, i) => ({
        name: w.name,
        value: w.value,
        itemStyle: { color: [c.success, c.primary, c.danger][i % 3] },
      })),
    }],
  })

  // 阶段分布
  mk(stagesRef, {
    tooltip: { trigger: 'axis' },
    grid: { left: 44, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: funnel.map((f) => f.stage), axisLabel: { interval: 0, rotate: 20 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: funnel.map((f) => f.count), itemStyle: { color: c.primary }, barMaxWidth: 40 }],
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
.card-head { display: flex; align-items: center; gap: 8px; }
.head-icon { color: var(--el-color-primary); }
</style>
