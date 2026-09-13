<template>
  <div class="page">
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:10px">
        <h2 class="page-title">{{ board?.name || '看板管理' }}</h2>
        <el-select v-if="boards.length > 1" v-model="currentBoardId" style="width:150px" @change="load">
          <el-option v-for="b in boards" :key="b.id" :value="b.id" :label="b.name" />
        </el-select>
      </div>
      <div class="page-toolbar">
        <el-button @click="addColumn"><el-icon><Plus /></el-icon>&nbsp;添加列</el-button>
        <el-button @click="openAddCard"><el-icon><Plus /></el-icon>&nbsp;添加卡片</el-button>
        <el-button type="primary" @click="createBoard"><el-icon><Plus /></el-icon>&nbsp;新建看板</el-button>
        <el-button v-if="boards.length > 1" type="danger" plain @click="deleteBoard"><el-icon><Delete /></el-icon>&nbsp;删除看板</el-button>
      </div>
    </div>

    <el-empty v-if="!boards.length" description="暂无看板，点击上方按钮创建">
      <el-button type="primary" @click="createBoard">新建看板</el-button>
    </el-empty>

    <div v-else class="kanban-board">
      <div v-for="(col, ci) in board.columns" :key="col.id" class="kanban-col"
        @dragover.prevent="dragoverCol = col.id"
        @dragleave="dragoverCol = null"
        @drop.prevent="onDrop($event, col.id); dragoverCol = null"
        :class="{ dragover: dragoverCol === col.id }">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:2px 4px 8px">
          <span style="font-weight:600;font-size:13px">{{ col.name }}</span>
          <el-tag size="small" type="info">{{ col.cards.length }}</el-tag>
        </div>
        <div v-for="card in col.cards" :key="card.id" class="kanban-card" draggable="true"
          :style="{ borderLeftColor: cardColor(card.color) }"
          @dragstart="onDragStart($event, card.id)">
          <div style="font-weight:500;font-size:13px;margin-bottom:4px">{{ card.title }}</div>
          <div v-if="card.description" class="muted" style="margin-bottom:4px">{{ card.description.substring(0, 60) }}</div>
          <div v-if="card.deadline" style="font-size:11px;color:var(--el-color-danger)">⏰ {{ fmtDate(card.deadline) }}</div>
          <div style="margin-top:6px;display:flex;justify-content:flex-end;gap:2px;align-items:center">
            <el-button size="small" text :disabled="ci === 0" @click="moveCardTo(card.id, board.columns[ci - 1]?.id)">‹</el-button>
            <el-button size="small" text :disabled="ci === board.columns.length - 1" @click="moveCardTo(card.id, board.columns[ci + 1]?.id)">›</el-button>
            <el-button size="small" text type="danger" @click="deleteCard(card.id)"><el-icon><Delete /></el-icon></el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加卡片 -->
    <el-dialog v-model="cardVisible" title="添加卡片" width="480px" destroy-on-close>
      <el-form :model="cardForm" label-width="80px">
        <el-form-item label="标题" required><el-input v-model="cardForm.title" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="cardForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="颜色">
              <el-select v-model="cardForm.color" style="width:100%">
                <el-option value="blue" label="蓝色" />
                <el-option value="green" label="绿色" />
                <el-option value="yellow" label="黄色" />
                <el-option value="red" label="红色" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="截止日期">
              <el-date-picker v-model="cardForm.deadline" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="cardVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCard">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { get, post, del, fmtDate } from '../api'
import { useCrawlStore } from '../stores/app'

const crawl = useCrawlStore()
const boards = ref([])
const board = ref(null)
const currentBoardId = ref(null)
const dragoverCol = ref(null)

const cardColor = (c) => ({ red: 'var(--el-color-danger)', yellow: 'var(--el-color-warning)', green: 'var(--el-color-success)' }[c] || 'var(--el-color-info)')

async function load() {
  boards.value = (await get('/kanban/boards')) || []
  if (!boards.value.length) { board.value = null; return }
  board.value = boards.value.find((b) => b.id === currentBoardId.value) || boards.value[0]
  currentBoardId.value = board.value.id
}

function onDragStart(e, cardId) { e.dataTransfer.setData('text', String(cardId)) }
async function onDrop(e, colId) {
  const cardId = e.dataTransfer.getData('text')
  if (!cardId) return
  await post(`/kanban/cards/${cardId}/move`, { column_id: colId })
  load()
}
async function moveCardTo(cardId, colId) {
  if (!colId) return
  await post(`/kanban/cards/${cardId}/move`, { column_id: colId })
  load()
}
async function createBoard() {
  const { value: name } = await ElMessageBox.prompt('看板名称:', '新建看板', { inputValue: '新看板' })
  const r = await post('/kanban/boards', { name })
  if (r && r.id) currentBoardId.value = r.id
  ElMessage.success('创建成功')
  load()
}
async function deleteBoard() {
  await ElMessageBox.confirm('确认删除该看板及其全部卡片？', '删除看板')
  await del(`/kanban/boards/${board.value.id}`)
  currentBoardId.value = null
  ElMessage.success('已删除')
  load()
}
async function addColumn() {
  const { value: name } = await ElMessageBox.prompt('列名称:', '添加列')
  await post(`/kanban/boards/${board.value.id}/columns`, { name })
  ElMessage.success('已添加')
  load()
}

const cardVisible = ref(false)
const cardForm = reactive({ title: '', description: '', color: 'blue', deadline: '' })
function openAddCard() {
  Object.assign(cardForm, { title: '', description: '', color: 'blue', deadline: '' })
  cardVisible.value = true
}
async function saveCard() {
  if (!cardForm.title) return ElMessage.error('请输入标题')
  const colId = board.value?.columns[0]?.id
  if (!colId) return ElMessage.error('无可用列')
  await post('/kanban/import', {
    board_id: board.value.id,
    items: [{ title: cardForm.title, description: cardForm.description, color: cardForm.color, deadline: cardForm.deadline || null }],
  })
  ElMessage.success('已添加')
  cardVisible.value = false
  load()
}
async function deleteCard(id) {
  await ElMessageBox.confirm('确认删除该卡片？', '删除卡片')
  await del(`/kanban/cards/${id}`)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => { await load(); crawl.checkRunning() })
</script>
