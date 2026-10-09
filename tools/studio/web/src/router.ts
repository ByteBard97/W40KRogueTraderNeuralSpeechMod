import { createRouter, createWebHistory } from 'vue-router'
import SpeakersView from './views/SpeakersView.vue'
import SpeakerView from './views/SpeakerView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/speakers' },
    { path: '/speakers', component: SpeakersView },
    { path: '/speakers/:slug', component: SpeakerView, props: true },
  ],
})
