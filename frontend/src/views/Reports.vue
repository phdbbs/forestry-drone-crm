<template>
  <div class="page">
    <div class="page-header"><h2 class="page-title">数据报表</h2></div>

    <el-row :gutter="16" class="card-block">
      <el-col :span="6" v-for="s in statCards" :key="s.label">
        <StatCard :label="s.label" :value="s.value" :icon="s.icon" :color="s.color" />
      </el-col>
    </el-row>

    <div class="chart-grid">
      <el-card shadow="never"><template #header><span style="font-weight:600">线索月度趋势</span></template><div ref="monthlyRef" class="chart-box"></div></el-card>
      <el-card shadow="never"><template #header><span style="font-weight:600">商机漏斗（金额）</span></template><div ref="funnelRef" class="chart-box"></div></el-card>
      <el-card shadow="never"><template #header><span style="font-weight:600">赢单/丢单分布</span></template><div ref="winLossRef" class="chart-box"></div></el-card>
      <el-card shadow="never"><template #header><span style="font-weight:600">阶段分布（商机数）</span></template><div ref="stagesRef" class="chart-box"></div></el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import StatCard from '../components/StatCard.vue'
import { get, STAGE_COLORS } from '../api'

const data = ref({})
const monthlyRef = ref(null)
const funnelRef = ref(null)
const winLossRef = ref(null)
const stagesRef = ref(null)
let charts = []

const statCards = computed(() => {
  const s = data.value.summary || {}
  return [
    { label: '总线索数', value: s.total_leads ?? 0, icon: 'Aim', color: 'var(--el-color-primary)' },
    { label: '商机总数', value: s.total_opportunities ?? 0, icon: 'DataAnalysis', color: '#3b82f6' },
    { label: '商机总金额', value: (s.total_amount ?? 0) + '万', icon: 'Coin', color: '#f59e0b' },
    { label: '转化率', value: (s.conversion_rate ?? 0) + '%', icon: 'TrendCharts', color: '#8b5cf6' },
  ]
})

function render() {
  const d = data.value
  const theme = getComputedStyle(document.documentElement).getPropertyValue('--crm-primary').trim() || '#2f7d4f'
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
    grid: { left: 40, right: 20, top: 20, bottom: 50 },
    xAxis: { type: 'category', data: (d.monthly_leads || []).map((m) => m.month) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '新增线索', type: 'line', smooth: true, areaStyle: { opacity: .1 }, data: (d.monthly_leads || []).map((m) => m.leads), itemStyle: { color: theme } },
      { name: '已转化', type: 'line', smooth: true, areaStyle: { opacity: .1 }, data: (d.monthly_leads || []).map((m) => m.converted), itemStyle: { color: '#f59e0b' } },
    ],
  })
  // 漏斗（横向柱）
  mk(funnelRef, {
    tooltip: { trigger: 'axis' },
    grid: { left: 90, right: 30, top: 10, bottom: 20 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: (d.funnel || []).map((f) => f.stage).reverse() },
    series: [{ type: 'bar', data: (d.funnel || []).map((f) => f.amount).reverse(), itemStyle: { color: (p) => STAGE_COLORS[(d.funnel || []).length - 1 - p.dataIndex % STAGE_COLORS.length] }, barMaxWidth: 24 }],
  })
  // 赢单/丢单
  mk(winLossRef, {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie', radius: ['40%', '65%'],
      data: (d.win_loss || []).map((w, i) => ({ name: w.name, value: w.value, itemStyle: { color: ['#166534', '#3b82f6', '#ef4444'][i % 3] } })),
    }],
  })
  // 阶段分布
  mk(stagesRef, {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: (d.funnel || []).map((f) => f.stage), axisLabel: { interval: 0, rotate: 20 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: (d.funnel || []).map((f, i) => ({ value: f.count, itemStyle: { color: STAGE_COLORS[i % STAGE_COLORS.length] } })), barMaxWidth: 40 }],
  })
}
function onResize() { charts.forEach((c) => c.resize()) }

onMounted(async () => {
  data.value = await get('/analytics')
  await nextTick()
  render()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  charts.forEach((c) => c.dispose())
  charts = []
})
</script>
