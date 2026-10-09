import { createRouter, createWebHistory } from 'vue-router'
import SpeakersView from './views/SpeakersView.vue'
import SpeakerView from './views/SpeakerView.vue'
import PoolsView from './views/PoolsView.vue'
import FxView from './views/FxView.vue'
import MatchesView from './views/MatchesView.vue'
import QaView from './views/QaView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/speakers' },
    { path: '/speakers', component: SpeakersView },
    { path: '/speakers/:slug', component: SpeakerView, props: true },
    { path: '/pools', component: PoolsView },
    { path: '/fx', component: FxView },
    { path: '/matches', component: MatchesView },
    { path: '/qa', component: QaView },
  ],
})
