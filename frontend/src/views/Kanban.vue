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
        <el-button @click="addColumn"><el-icon><Plus /></el-icon>&nbsp;添加列表</el-button>
        <el-button type="primary" @click="createBoard"><el-icon><Plus /></el-icon>&nbsp;新建看板</el-button>
        <el-button v-if="boards.length > 1" type="danger" plain @click="deleteBoard"><el-icon><Delete /></el-icon>&nbsp;删除看板</el-button>
      </div>
    </div>

    <el-empty v-if="!boards.length" description="暂无看板，点击上方按钮创建">
      <el-button type="primary" @click="createBoard">新建看板</el-button>
    </el-empty>

    <draggable v-else v-model="board.columns" item-key="id" handle=".col-drag-handle"
      group="columns" animation="200" ghost-class="col-ghost" class="kanban-board"
      @end="onColumnDrop">
      <template #item="{ element: col, index: ci }">
        <div class="kanban-col" :data-col="col.id">
          <!-- 列头：拖拽手柄 + 重命名/删除 -->
          <div class="col-header col-drag-handle">
            <span class="col-title" @click.stop>{{ col.name }}</span>
            <el-dropdown trigger="click" @command="cmd => colMenu(cmd, col)">
              <el-icon class="col-more" @click.stop><MoreFilled /></el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="rename">重命名列表</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除列表（含卡片）</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>

          <!-- 卡片区：跨列/列内拖拽 -->
          <draggable :list="col.cards" item-key="id" group="cards" animation="200"
            ghost-class="card-ghost" drag-class="card-dragging"
            class="kanban-cards" :data-col="col.id"
            @end="onCardDrop">
            <template #item="{ element: card }">
              <div class="kanban-card" :data-card="card.id"
                :style="{ borderLeftColor: cardColor(card.color) }"
                @click="openCard(card)">
                <div class="card-title">{{ card.title }}</div>
                <div v-if="card.description" class="muted card-desc">{{ card.description }}</div>
                <div class="card-foot">
                  <el-tag v-if="card.color && card.color !== 'blue'" size="small" :color="cardColor(card.color)" effect="dark" style="border:none;height:16px;padding:0 6px;font-size:10px">
                    {{ colorLabel(card.color) }}
                  </el-tag>
                  <span v-if="card.deadline" class="card-deadline" :class="{ overdue: isOverdue(card.deadline) }">
                    <el-icon :size="11"><AlarmClock /></el-icon>{{ fmtDate(card.deadline) }}
                  </span>
                  <span v-if="card.source_type" class="muted" style="font-size:10px">🔗 关联</span>
                </div>
              </div>
            </template>
          </draggable>

          <!-- 列内快速添加 -->
          <div class="quick-add">
            <template v-if="addingCol === col.id">
              <el-input v-model="quickTitle" type="textarea" :rows="2" size="small"
                placeholder="输入卡片标题，Enter 保存" ref="quickInput" @keydown.enter.prevent="quickSave(col)" />
              <div style="display:flex;gap:6px;margin-top:6px">
                <el-button type="primary" size="small" @click="quickSave(col)">添加卡片</el-button>
                <el-button size="small" @click="addingCol = null">取消</el-button>
              </div>
            </template>
            <template v-else>
              <el-button text size="small" class="quick-add-btn" @click="startQuickAdd(col)">
                <el-icon><Plus /></el-icon>&nbsp;添加卡片
              </el-button>
            </template>
          </div>
        </div>
      </template>
    </draggable>

    <!-- 列表尾部添加列表 -->
    <div v-if="board" class="add-list-wrap">
      <template v-if="addingList">
        <el-input v-model="newListName" size="small" placeholder="列表名称" @keydown.enter="saveNewList" style="width:200px" />
        <el-button type="primary" size="small" @click="saveNewList" style="margin-left:6px">添加</el-button>
      </template>
      <el-button v-else text size="small" @click="addingList = true"><el-icon><Plus /></el-icon>&nbsp;添加列表</el-button>
    </div>

    <!-- 卡片详情/编辑 -->
    <el-dialog v-model="cardVisible" title="卡片详情" width="520px" destroy-on-close>
      <el-form :model="cardForm" label-width="80px">
        <el-form-item label="标题" required><el-input v-model="cardForm.title" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="cardForm.description" type="textarea" :rows="4" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="标签颜色">
              <el-select v-model="cardForm.color" style="width:100%">
                <el-option value="blue" label="蓝" />
                <el-option value="green" label="绿" />
                <el-option value="yellow" label="黄" />
                <el-option value="red" label="红" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="截止日期">
              <el-date-picker v-model="cardForm.deadline" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <div v-if="cardForm.source_type" class="muted" style="font-size:12px">
          来源：{{ sourceLabel(cardForm.source_type) }}（由业务自动生成，移动列不影响关联）
        </div>
      </el-form>
      <template #footer>
        <el-button type="danger" plain @click="deleteCurrentCard"><el-icon><Delete /></el-icon>&nbsp;删除</el-button>
        <el-button @click="cardVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCardDetail">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, MoreFilled, AlarmClock } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import { get, post, put, del, fmtDate } from '../api'
import { useCrawlStore } from '../stores/app'

const crawl = useCrawlStore()
const boards = ref([])
const board = ref(null)
const currentBoardId = ref(null)

const cardColor = (c) => ({ red: '#ef4444', yellow: '#f59e0b', green: '#22c55e' }[c] || '#94a3b8')
const colorLabel = (c) => ({ red: '紧急', yellow: '关注', green: '顺利' }[c] || '')
const sourceLabel = (t) => ({ activity: '日常联络', followup: '联络计划', stage: '商机阶段', opportunity: '商机' }[t] || t)
const isOverdue = (d) => d && fmtDate(d) < new Date().toISOString().slice(0, 10)

async function load() {
  boards.value = (await get('/kanban/boards')) || []
  if (!boards.value.length) { board.value = null; return }
  board.value = boards.value.find((b) => b.id === currentBoardId.value) || boards.value[0]
  currentBoardId.value = board.value.id
}

// ---- 卡片拖拽：本地列表已被 vuedraggable 更新，持久化目标列+位置 ----
async function onCardDrop(evt) {
  const toColEl = evt.to.closest('.kanban-col')
  const colId = parseInt(toColEl?.dataset.col)
  const cardId = parseInt(evt.item.dataset.card)
  if (!colId || !cardId) return
  await post(`/kanban/cards/${cardId}/move`, { column_id: colId, position: evt.newIndex })
}

// ---- 列拖拽排序 ----
async function onColumnDrop() {
  if (!board.value) return
  await post(`/kanban/boards/${board.value.id}/columns/reorder`, {
    ids: board.value.columns.map((c) => c.id),
  })
}

// ---- 列管理 ----
async function colMenu(cmd, col) {
  if (cmd === 'rename') {
    const { value: name } = await ElMessageBox.prompt('列表名称:', '重命名列表', { inputValue: col.name })
    await put(`/kanban/columns/${col.id}`, { name })
    col.name = name
    ElMessage.success('已重命名')
  } else if (cmd === 'delete') {
    await ElMessageBox.confirm(`确认删除列表「${col.name}」及其全部 ${col.cards.length} 张卡片？`, '删除列表', { type: 'warning' })
    await del(`/kanban/columns/${col.id}`)
    ElMessage.success('已删除')
    load()
  }
}
async function addColumn() {
  const { value: name } = await ElMessageBox.prompt('列表名称:', '添加列表')
  await post(`/kanban/boards/${board.value.id}/columns`, { name })
  ElMessage.success('已添加')
  load()
}
const addingList = ref(false)
const newListName = ref('')
async function saveNewList() {
  if (!newListName.value.trim()) return
  await post(`/kanban/boards/${board.value.id}/columns`, { name: newListName.value.trim() })
  newListName.value = ''
  addingList.value = false
  ElMessage.success('已添加')
  load()
}

// ---- 快速添加卡片 ----
const addingCol = ref(null)
const quickTitle = ref('')
const quickInput = ref(null)
function startQuickAdd(col) {
  addingCol.value = col.id
  quickTitle.value = ''
  nextTick(() => quickInput.value?.focus?.())
}
async function quickSave(col) {
  if (!quickTitle.value.trim()) return
  await post('/kanban/cards', { column_id: col.id, title: quickTitle.value.trim() })
  const cards = (await get('/kanban/boards')).find((b) => b.id === board.value.id)?.columns.find((c) => c.id === col.id)?.cards || []
  col.cards = cards
  quickTitle.value = ''
  addingCol.value = null
  ElMessage.success('已添加')
}

// ---- 卡片详情编辑 ----
const cardVisible = ref(false)
const cardForm = reactive({ id: null, title: '', description: '', color: 'blue', deadline: '', source_type: '' })
function openCard(card) {
  Object.assign(cardForm, {
    id: card.id, title: card.title, description: card.description || '',
    color: card.color || 'blue', deadline: fmtDate(card.deadline) || '', source_type: card.source_type || '',
  })
  cardVisible.value = true
}
async function saveCardDetail() {
  if (!cardForm.title.trim()) return ElMessage.error('请输入标题')
  const r = await put(`/kanban/cards/${cardForm.id}`, {
    title: cardForm.title, description: cardForm.description,
    color: cardForm.color, deadline: cardForm.deadline || null,
  })
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已保存')
  cardVisible.value = false
  load()
}
async function deleteCurrentCard() {
  await ElMessageBox.confirm('确认删除该卡片？', '删除卡片')
  await del(`/kanban/cards/${cardForm.id}`)
  ElMessage.success('已删除')
  cardVisible.value = false
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
  await ElMessageBox.confirm('确认删除该看板及其全部列表和卡片？', '删除看板', { type: 'warning' })
  await del(`/kanban/boards/${board.value.id}`)
  currentBoardId.value = null
  ElMessage.success('已删除')
  load()
}

onMounted(async () => { await load(); crawl.checkRunning() })
</script>

<style scoped>
.kanban-board { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 12px; align-items: flex-start; }
.kanban-col {
  background: #eef1ef; border-radius: 10px; width: 280px; flex-shrink: 0;
  padding: 10px; display: flex; flex-direction: column; max-height: calc(100vh - 180px);
}
.col-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 2px 4px 10px; cursor: grab; border-radius: 6px;
}
.col-header:active { cursor: grabbing; }
.col-title { font-weight: 600; font-size: 13px; }
.col-more { cursor: pointer; color: #8a9a90; padding: 2px; }
.col-more:hover { color: #1f2d24; }
.kanban-cards { flex: 1; overflow-y: auto; min-height: 30px; }
.kanban-card {
  background: #fff; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px;
  box-shadow: 0 1px 2px rgba(0,0,0,.08); cursor: pointer; border-left: 4px solid transparent;
}
.kanban-card:hover { box-shadow: 0 3px 8px rgba(0,0,0,.12); }
.card-title { font-weight: 500; font-size: 13px; }
.card-desc { margin-top: 4px; font-size: 12px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card-foot { display: flex; align-items: center; gap: 6px; margin-top: 6px; }
.card-deadline {
  display: inline-flex; align-items: center; gap: 3px; font-size: 11px;
  color: var(--el-color-primary); background: var(--crm-primary-bg);
  padding: 1px 6px; border-radius: 4px;
}
.card-deadline.overdue { color: var(--el-color-danger); background: #fef2f2; }
.quick-add { margin-top: 8px; }
.quick-add-btn { width: 100%; justify-content: flex-start; color: #6b7d71; }
.add-list-wrap { flex-shrink: 0; width: 220px; }
.col-ghost { opacity: .4; }
.card-ghost { opacity: .4; transform: rotate(3deg); }
.card-dragging { transform: rotate(3deg); }
</style>
