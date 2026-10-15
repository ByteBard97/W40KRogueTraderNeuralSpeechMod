import { createPinia } from 'pinia'
import { createApp } from 'vue'
import DemoApp from './DemoApp.vue'

createApp(DemoApp).use(createPinia()).mount('#app')
