<template>
  <el-dialog v-model="visible" title="快速新增联系人" width="440px" destroy-on-close append-to-body>
    <el-form label-width="80px" @submit.prevent>
      <el-form-item label="所属客户">
        <el-input :model-value="customerName || '（未选客户，可先保存联系人）'" disabled />
      </el-form-item>
      <el-form-item label="姓名" required>
        <el-input v-model="name" placeholder="联系人姓名" @keydown.enter="save" />
      </el-form-item>
      <el-form-item label="电话">
        <el-input v-model="phone" placeholder="手机/座机" @keydown.enter="save" />
      </el-form-item>
      <el-form-item label="职位">
        <el-input v-model="title" placeholder="如：办公室主任（可后补）" @keydown.enter="save" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存并选用</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
// 表单内快捷新增联系人：保存后自动 emit 给调用方选中，不中断当前填写流程
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { post } from '../api'
import { useDictStore } from '../stores/app'

const dict = useDictStore()
const visible = ref(false)
const saving = ref(false)
const name = ref('')
const phone = ref('')
const title = ref('')

const props = defineProps({
  customerId: { type: [Number, String], default: null },
  customerName: { type: String, default: '' },
})
const emit = defineEmits(['created'])

function open() {
  name.value = phone.value = title.value = ''
  visible.value = true
}
async function save() {
  if (!name.value.trim()) return ElMessage.error('请输入姓名')
  saving.value = true
  const r = await post('/contacts', {
    name: name.value.trim(),
    phone: phone.value.trim(),
    title: title.value.trim(),
    customer_id: props.customerId || null,
  })
  saving.value = false
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('联系人已创建')
  visible.value = false
  await dict.loadContacts()
  emit('created', r)
}
defineExpose({ open })
</script>
