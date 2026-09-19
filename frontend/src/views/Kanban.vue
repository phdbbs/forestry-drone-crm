<template>
  <div class="page">
    <div class="page-header">
      <div class="title-group">
        <h2 class="page-title">{{ board?.name || '看板管理' }}</h2>
        <el-select v-if="boards.length > 1" v-model="currentBoardId" class="board-select" @change="load">
          <el-option v-for="b in boards" :key="b.id" :value="b.id" :label="b.name" />
        </el-select>
      </div>
      <div class="page-toolbar">
        <el-button :icon="Plus" @click="openNameDialog('addColumn')">添加列表</el-button>
        <el-button type="primary" :icon="Plus" @click="openNameDialog('createBoard')">新建看板</el-button>
        <el-button v-if="boards.length > 1" type="danger" plain :icon="Delete" @click="deleteBoard">删除看板</el-button>
      </div>
    </div>

    <el-card v-loading="loading" shadow="never" class="board-card">
      <el-empty v-if="!loading && !boards.length" description="暂无看板">
        <el-button type="primary" :icon="Plus" @click="openNameDialog('createBoard')">新建看板</el-button>
      </el-empty>

      <draggable
        v-else-if="board"
        v-model="board.columns"
        item-key="id"
        handle=".col-drag-handle"
        group="columns"
        animation="200"
        ghost-class="col-ghost"
        class="kanban-board"
        @end="onColumnDrop"
      >
        <template #item="{ element: col }">
          <div class="kanban-col" :data-col="col.id">
            <!-- 列头：拖拽手柄 + 更多操作 -->
            <div class="col-header col-drag-handle">
              <span class="col-title">{{ col.name }}</span>
              <el-dropdown trigger="click" @command="cmd => colMenu(cmd, col)">
                <el-button text size="small" :icon="MoreFilled" class="col-more" @click.stop />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="rename">重命名列表</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>删除列表（含卡片）</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>

            <!-- 卡片区：跨列 / 列内拖拽 -->
            <draggable
              :list="col.cards"
              item-key="id"
              group="cards"
              animation="200"
              ghost-class="card-ghost"
              drag-class="card-dragging"
              class="kanban-cards"
              :data-col="col.id"
              @end="onCardDrop"
            >
              <template #item="{ element: card }">
                <div
                  class="kanban-card"
                  :class="`card-accent--${card.color || 'blue'}`"
                  :data-card="card.id"
                  @click="openCard(card)"
                >
                  <div class="card-title">{{ card.title }}</div>
                  <div v-if="card.description" class="card-desc">{{ card.description }}</div>
                  <div class="card-foot">
                    <el-tag
                      v-if="card.color && card.color !== 'blue'"
                      size="small"
                      :type="tagType(card.color)"
                      effect="light"
                    >
                      {{ colorLabel(card.color) }}
                    </el-tag>
                    <span v-if="card.deadline" class="card-deadline" :class="{ overdue: isOverdue(card.deadline) }">
                      <el-icon :size="12"><AlarmClock /></el-icon>{{ fmtDate(card.deadline) }}
                    </span>
                    <span v-if="card.source_type" class="card-source">
                      <el-icon :size="12"><Link /></el-icon>关联
                    </span>
                  </div>
                </div>
              </template>
            </draggable>

            <!-- 列内快速添加 -->
            <div class="quick-add">
              <template v-if="addingCol === col.id">
                <el-input
                  v-model="quickTitle"
                  type="textarea"
                  :rows="2"
                  size="small"
                  autofocus
                  placeholder="输入卡片标题，Enter 保存"
                  @keydown.enter.prevent="quickSave(col)"
                />
                <el-space class="quick-actions">
                  <el-button type="primary" size="small" @click="quickSave(col)">添加卡片</el-button>
                  <el-button size="small" @click="addingCol = null">取消</el-button>
                </el-space>
              </template>
              <el-button v-else text size="small" class="quick-add-btn" :icon="Plus" @click="startQuickAdd(col)">
                添加卡片
              </el-button>
            </div>
          </div>
        </template>
      </draggable>
    </el-card>

    <!-- 统一命名对话框：新建看板 / 添加列表 / 重命名列表 -->
    <el-dialog v-model="nameDialog.visible" :title="nameDialog.title" width="420px" destroy-on-close>
      <el-form ref="nameFormRef" :model="nameDialog" :rules="nameRules" label-width="72px" @submit.prevent="submitName">
        <el-form-item label="名称" prop="name">
          <el-input v-model="nameDialog.name" maxlength="20" show-word-limit placeholder="请输入名称" @keyup.enter="submitName" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="nameDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="nameDialog.loading" @click="submitName">确定</el-button>
      </template>
    </el-dialog>

    <!-- 卡片详情 / 编辑 -->
    <el-dialog v-model="cardVisible" title="卡片详情" width="520px" destroy-on-close class="card-dialog">
      <el-form ref="cardFormRef" :model="cardForm" :rules="cardRules" label-width="80px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="cardForm.title" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="cardForm.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="标签颜色">
              <el-select v-model="cardForm.color" class="w-full">
                <el-option value="blue" label="蓝" />
                <el-option value="green" label="绿" />
                <el-option value="yellow" label="黄" />
                <el-option value="red" label="红" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="截止日期">
              <el-date-picker v-model="cardForm.deadline" type="date" value-format="YYYY-MM-DD" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-alert v-if="cardForm.source_type" type="info" :closable="false" show-icon>
          来源：{{ sourceLabel(cardForm.source_type) }}（由业务自动生成，移动列不影响关联）
        </el-alert>
      </el-form>
      <template #footer>
        <el-button type="danger" plain :icon="Delete" class="footer-left" @click="deleteCurrentCard">删除</el-button>
        <el-button @click="cardVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingCard" @click="saveCardDetail">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, MoreFilled, AlarmClock, Link } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import { get, getList, post, put, del, fmtDate } from '../api'
import { useCrawlStore } from '../stores/app'

const crawl = useCrawlStore()
const boards = ref([])
const board = ref(null)
const currentBoardId = ref(null)
const loading = ref(false)

// 颜色一律走 Element Plus 语义色，不再硬编码十六进制
const tagType = (c) => ({ red: 'danger', yellow: 'warning', green: 'success' }[c] || 'info')
const colorLabel = (c) => ({ red: '紧急', yellow: '关注', green: '顺利' }[c] || '')
const sourceLabel = (t) => ({ activity: '日常联络', followup: '联络计划', stage: '商机阶段', opportunity: '商机' }[t] || t)
const isOverdue = (d) => d && fmtDate(d) < new Date().toISOString().slice(0, 10)

async function load() {
  loading.value = true
  boards.value = await getList('/kanban/boards')
  loading.value = false
  if (!boards.value.length) { board.value = null; return }
  board.value = boards.value.find((b) => b.id === currentBoardId.value) || boards.value[0]
  currentBoardId.value = board.value.id
}

// ---- 卡片拖拽：本地列表已被 vuedraggable 更新，持久化目标列 + 位置 ----
async function onCardDrop(evt) {
  const toColEl = evt.to.closest('.kanban-col')
  const colId = parseInt(toColEl?.dataset.col)
  const cardId = parseInt(evt.item.dataset.card)
  if (!colId || !cardId) return
  const r = await post(`/kanban/cards/${cardId}/move`, { column_id: colId, position: evt.newIndex })
  if (r.error) ElMessage.error(r.error)
}

// ---- 列拖拽排序 ----
async function onColumnDrop() {
  if (!board.value) return
  const r = await post(`/kanban/boards/${board.value.id}/columns/reorder`, {
    ids: board.value.columns.map((c) => c.id),
  })
  if (r.error) ElMessage.error(r.error)
}

// ---- 统一命名对话框（替代 ElMessageBox.prompt） ----
// 原实现用 ElMessageBox.prompt 收集名称，用户点「取消」时 value 为 null，
// 代码未判断便继续提交，会创建/保存出名称为 null 的列表或看板。
const nameFormRef = ref(null)
const nameDialog = reactive({ visible: false, mode: '', title: '', name: '', loading: false, column: null })
const nameRules = {
  name: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { max: 20, message: '不超过 20 个字符', trigger: 'blur' },
  ],
}

function openNameDialog(mode, col) {
  nameDialog.mode = mode
  nameDialog.column = col || null
  nameDialog.name = mode === 'renameColumn' ? (col?.name || '') : (mode === 'createBoard' ? '新看板' : '')
  nameDialog.title = { createBoard: '新建看板', addColumn: '添加列表', renameColumn: '重命名列表' }[mode]
  nameDialog.loading = false
  nameDialog.visible = true
  nextTick(() => nameFormRef.value?.clearValidate())
}

async function submitName() {
  if (!nameFormRef.value) return
  const valid = await nameFormRef.value.validate().catch(() => false)
  if (!valid) return
  const name = nameDialog.name.trim()
  nameDialog.loading = true
  try {
    if (nameDialog.mode === 'createBoard') {
      const r = await post('/kanban/boards', { name })
      if (r.error) return ElMessage.error(r.error)
      if (r.id) currentBoardId.value = r.id
      ElMessage.success('创建成功')
      nameDialog.visible = false
      await load()
    } else if (nameDialog.mode === 'addColumn') {
      const r = await post(`/kanban/boards/${board.value.id}/columns`, { name })
      if (r.error) return ElMessage.error(r.error)
      ElMessage.success('已添加')
      nameDialog.visible = false
      await load()
    } else {
      const r = await put(`/kanban/columns/${nameDialog.column.id}`, { name })
      if (r.error) return ElMessage.error(r.error)
      nameDialog.column.name = name
      ElMessage.success('已重命名')
      nameDialog.visible = false
    }
  } finally {
    nameDialog.loading = false
  }
}

// ---- 列管理 ----
async function colMenu(cmd, col) {
  if (cmd === 'rename') {
    openNameDialog('renameColumn', col)
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除列表「${col.name}」及其全部 ${col.cards.length} 张卡片？`, '删除列表', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/kanban/columns/${col.id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除')
  load()
}

// ---- 快速添加卡片 ----
const addingCol = ref(null)
const quickTitle = ref('')
function startQuickAdd(col) {
  addingCol.value = col.id
  quickTitle.value = ''
}
async function quickSave(col) {
  const title = quickTitle.value.trim()
  if (!title) return
  const r = await post('/kanban/cards', { column_id: col.id, title })
  if (r.error) return ElMessage.error(r.error)
  const fresh = await getList('/kanban/boards')
  const target = fresh.find((b) => b.id === board.value.id)?.columns.find((c) => c.id === col.id)
  if (target) col.cards = target.cards
  quickTitle.value = ''
  addingCol.value = null
  ElMessage.success('已添加')
}

// ---- 卡片详情编辑 ----
const cardVisible = ref(false)
const cardFormRef = ref(null)
const savingCard = ref(false)
const cardForm = reactive({ id: null, title: '', description: '', color: 'blue', deadline: '', source_type: '' })
const cardRules = { title: [{ required: true, message: '请输入标题', trigger: 'blur' }] }

function openCard(card) {
  Object.assign(cardForm, {
    id: card.id, title: card.title, description: card.description || '',
    color: card.color || 'blue', deadline: fmtDate(card.deadline) || '', source_type: card.source_type || '',
  })
  cardVisible.value = true
  nextTick(() => cardFormRef.value?.clearValidate())
}

async function saveCardDetail() {
  if (!cardFormRef.value) return
  const valid = await cardFormRef.value.validate().catch(() => false)
  if (!valid) return
  savingCard.value = true
  try {
    const r = await put(`/kanban/cards/${cardForm.id}`, {
      title: cardForm.title, description: cardForm.description,
      color: cardForm.color, deadline: cardForm.deadline || null,
    })
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success('已保存')
    cardVisible.value = false
    load()
  } finally {
    savingCard.value = false
  }
}

async function deleteCurrentCard() {
  try {
    await ElMessageBox.confirm('确认删除该卡片？', '删除卡片', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/kanban/cards/${cardForm.id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除')
  cardVisible.value = false
  load()
}

async function deleteBoard() {
  try {
    await ElMessageBox.confirm('确认删除该看板及其全部列表和卡片？', '删除看板', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/kanban/boards/${board.value.id}`)
  if (r.error) return ElMessage.error(r.error)
  currentBoardId.value = null
  ElMessage.success('已删除')
  load()
}

onMounted(async () => { await load(); crawl.checkRunning() })
</script>

<style scoped>
.title-group { display: flex; align-items: center; gap: 10px; }
.board-select { width: 160px; }
.w-full { width: 100%; }
.board-card { min-height: 240px; }
.board-card :deep(.el-card__body) { padding: 12px; }

.kanban-board { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 4px; align-items: flex-start; }
.kanban-col {
  background: var(--el-fill-color-light);
  border-radius: var(--el-border-radius-base);
  width: 280px; flex: 0 0 280px;
  padding: 10px; display: flex; flex-direction: column;
  max-height: calc(100vh - 240px);
}
.col-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 2px 2px 10px 6px; cursor: grab;
}
.col-header:active { cursor: grabbing; }
.col-title { font-weight: 600; font-size: 13px; color: var(--el-text-color-primary); }
.col-more { color: var(--el-text-color-secondary); }

.kanban-cards { flex: 1; overflow-y: auto; min-height: 30px; }
.kanban-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-left: 3px solid var(--el-color-primary);
  border-radius: var(--el-border-radius-base);
  padding: 10px 12px; margin-bottom: 8px;
  cursor: pointer;
  transition: box-shadow .15s, border-color .15s;
}
.kanban-card:hover { box-shadow: var(--el-box-shadow-light); }
.card-accent--red { border-left-color: var(--el-color-danger); }
.card-accent--yellow { border-left-color: var(--el-color-warning); }
.card-accent--green { border-left-color: var(--el-color-success); }
.card-accent--blue { border-left-color: var(--el-color-primary); }

.card-title { font-weight: 600; font-size: 13px; color: var(--el-text-color-primary); line-height: 1.45; }
.card-desc {
  margin-top: 6px; font-size: 12px; line-height: 1.55;
  color: var(--el-text-color-secondary); background: var(--el-fill-color-lighter);
  border-radius: 5px; padding: 5px 8px;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.card-foot { display: flex; align-items: center; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.card-deadline, .card-source {
  display: inline-flex; align-items: center; gap: 3px; font-size: 11px;
  color: var(--el-text-color-secondary);
}
.card-deadline.overdue { color: var(--el-color-danger); }

.quick-add { margin-top: 8px; }
.quick-actions { margin-top: 6px; }
.quick-add-btn { width: 100%; justify-content: flex-start; color: var(--el-text-color-secondary); }
.col-ghost { opacity: .4; }
.card-ghost { opacity: .4; }
.card-dragging { transform: rotate(2deg); }
</style>

<style>
/* el-dialog 默认 teleport 到 body，scoped 样式无法命中，故用全局块 */
.card-dialog .el-dialog__footer { display: flex; }
.card-dialog .footer-left { margin-right: auto; }
</style>
