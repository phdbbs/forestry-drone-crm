import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './styles/theme.css'
import App from './App.vue'
import router from './router'

// 图标按需注册：仅注册模板中以字符串名动态引用的图标（全局约 300 个全部注册会使
// tree-shaking 失效、首包膨胀约 100KB+；各视图局部 import 的图标不受影响）
import {
  Aim, Coin, DataAnalysis, Phone, TrendCharts, Warning,
  Odometer, User, OfficeBuilding, AlarmClock, Grid, Setting,
  ArrowDown, ArrowUp, ArrowLeft, ArrowRight,
  Top, Bottom, Minus, InfoFilled, Plus, Delete, Refresh, Download, Lightning,
  MoreFilled, Edit, Search, Close, Check, Bell, Fold, Expand,
} from '@element-plus/icons-vue'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
for (const icon of [Aim, Coin, DataAnalysis, Phone, TrendCharts, Warning,
  Odometer, User, OfficeBuilding, AlarmClock, Grid, Setting,
  ArrowDown, ArrowUp, ArrowLeft, ArrowRight,
  Top, Bottom, Minus, InfoFilled, Plus, Delete, Refresh, Download, Lightning,
  MoreFilled, Edit, Search, Close, Check, Bell, Fold, Expand]) {
  app.component(icon.name, icon)
}
app.mount('#app')
