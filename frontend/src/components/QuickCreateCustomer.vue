<template>
  <el-dialog v-model="visible" title="快速新增客户" width="440px" destroy-on-close append-to-body>
    <el-form label-width="80px" @submit.prevent>
      <el-form-item label="客户名称" required>
        <el-input v-model="name" placeholder="单位全称" @keydown.enter="save" />
      </el-form-item>
      <el-form-item label="地区">
        <el-input v-model="region" placeholder="如：浙江丽水（可后补）" @keydown.enter="save" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="type" clearable style="width:100%" placeholder="可后补">
          <el-option v-for="t in typeOptions" :key="t" :value="t" :label="t" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存并选用</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
// 表单内快捷新增客户：保存后 emit 给调用方选中
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { post } from '../api'
import { useDictStore } from '../stores/app'

const dict = useDictStore()
const visible = ref(false)
const saving = ref(false)
const name = ref('')
const region = ref('')
const type = ref('')
const FALLBACK_TYPES = ['政府部门', '事业单位', '国有企业', '民营企业', '科研院所', '运营商', '科技公司']
const typeOptions = computed(() => dict.options.customer_types?.length ? dict.options.customer_types : FALLBACK_TYPES)

const emit = defineEmits(['created'])

function open() {
  name.value = region.value = type.value = ''
  visible.value = true
}
async function save() {
  if (!name.value.trim()) return ElMessage.error('请输入客户名称')
  saving.value = true
  const r = await post('/customers', { name: name.value.trim(), region: region.value.trim(), type: type.value })
  saving.value = false
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('客户已创建')
  visible.value = false
  await dict.loadCustomers()
  emit('created', r)
}
defineExpose({ open })
</script>
