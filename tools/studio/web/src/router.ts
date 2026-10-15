import { createRouter, createWebHistory } from 'vue-router'
import SpeakersView from './views/SpeakersView.vue'
import SpeakerView from './views/SpeakerView.vue'
import PoolsView from './views/PoolsView.vue'
import FxView from './views/FxView.vue'
import MatchesView from './views/MatchesView.vue'
import QaView from './views/QaView.vue'
import CastingView from './views/CastingView.vue'
import VoicesView from './views/VoicesView.vue'
import AssignmentsView from './views/AssignmentsView.vue'
import LabView from './views/LabView.vue'

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
    { path: '/casting', component: CastingView },
    { path: '/voices', component: VoicesView },
    { path: '/assignments', component: AssignmentsView },
    { path: '/lab', component: LabView },
    // Dev only (or a build with VITE_STYLEGUIDE=1): every shared component on one page.
    ...(import.meta.env.DEV || import.meta.env.VITE_STYLEGUIDE ? [{ path: '/styleguide', component: () => import('./views/StyleguideView.vue') }] : []),
  ],
})
