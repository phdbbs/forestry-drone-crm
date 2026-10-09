<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <div class="brand-mark">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3 L4 8 v8 l8 5 8-5 V8 Z" />
            <path d="M12 8 v8 M8 12 h8" />
          </svg>
        </div>
        <div>
          <div class="brand-name">林业无人机 CRM</div>
          <div class="brand-sub mono">ACCESS REQUIRED</div>
        </div>
      </div>

      <div class="login-title">{{ isSetup ? '创建管理员账号' : '账号登录' }}</div>
      <p class="login-hint">
        {{ isSetup
          ? '这是首次进入：创建第一个管理员账号，之后由管理员在「系统设置 → 账号管理」里为同事建号。'
          : '使用管理员分配的账号与口令登录；会话失效后需重新登录。' }}
      </p>

      <el-form @submit.prevent="submit">
        <el-form-item>
          <el-input
            ref="userRef"
            v-model="username"
            :placeholder="isSetup ? '管理员账号名，如 admin' : '账号名'"
            size="large"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            ref="pwdRef"
            v-model="password"
            :type="showPwd ? 'text' : 'password'"
            :placeholder="isSetup ? '至少 6 位' : '登录口令'"
            size="large"
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item v-if="isSetup">
          <el-input
            v-model="confirm"
            :type="showPwd ? 'text' : 'password'"
            placeholder="再次输入以确认"
            size="large"
            autocomplete="new-password"
          />
        </el-form-item>
        <label class="login-show">
          <el-checkbox v-model="showPwd" size="small">显示口令</el-checkbox>
        </label>
        <el-button type="primary" class="login-submit" size="large" :loading="busy" native-type="submit" block>
          {{ isSetup ? '创建并进入' : '登录' }}
        </el-button>
      </el-form>

      <el-alert v-if="message" :title="message" type="error" :closable="false" show-icon class="login-alert" />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const password = ref('')
const confirm = ref('')
const showPwd = ref(false)
const busy = ref(false)
const message = ref('')
const userRef = ref(null)
const pwdRef = ref(null)

const isSetup = computed(() => auth.authEnabled && !auth.configured)

async function submit() {
  message.value = ''
  const account = username.value.trim()
  if (!account) return (message.value = '请填写账号名')
  if (isSetup.value) {
    if (password.value.length < 6) return (message.value = '口令至少 6 位')
    if (password.value !== confirm.value) return (message.value = '两次输入的口令不一致')
  }
  busy.value = true
  const err = isSetup.value
    ? await auth.setup(account, password.value)
    : await auth.login(account, password.value)
  busy.value = false
  if (err) {
    message.value = err
    // 管理员账号已被他人创建时，本地状态要跟上，否则一直停在「初始化」分支
    await auth.fetchStatus()
    return
  }
  router.replace('/dashboard')
}

onMounted(async () => {
  if (!auth.ready) await auth.fetchStatus()
  if (isSetup.value) username.value = 'admin'
  await nextTick()
  if (username.value) pwdRef.value?.focus?.()
  else userRef.value?.focus?.()
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
  background:
    radial-gradient(1000px 420px at 50% -10%, var(--crm-pine-25, #eef7f2), transparent 70%),
    var(--crm-bg-app);
}
.login-card {
  width: 100%; max-width: 380px;
  background: var(--el-bg-color);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  box-shadow: var(--crm-shadow-sm);
  padding: 26px 26px 22px;
}
.login-brand { display: flex; align-items: center; gap: 10px; margin-bottom: 22px; }
.brand-mark {
  width: 32px; height: 32px; border-radius: 9px; flex-shrink: 0;
  background: linear-gradient(135deg, var(--crm-pine-500), var(--crm-pine-700));
  color: #fff; display: flex; align-items: center; justify-content: center;
}
.brand-name { font-size: 14px; font-weight: 700; color: var(--crm-fg-1); line-height: 1.2; }
.brand-sub { font-size: 10.5px; color: var(--crm-fg-4); letter-spacing: 0.14em; margin-top: 2px; }
.login-title { font-size: 19px; font-weight: 650; color: var(--crm-fg-1); letter-spacing: -0.01em; }
.login-hint { margin: 8px 0 18px; font-size: 13px; color: var(--crm-fg-3); line-height: 1.65; }
.login-show { display: block; margin: -6px 0 14px; }
.login-submit { width: 100%; }
.login-alert { margin-top: 14px; }
</style>
