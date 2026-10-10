<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { shortId } from '../../composables/useDesign'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { useWorkbenchAction } from '../../composables/useWorkbenchActions'
import { useSpeakersStore } from '../../stores/speakers'
import { ago } from '../../utils/ago'
import Btn from '../ui/Btn.vue'
import Icon from '../ui/Icon.vue'
import Kbd from '../ui/Kbd.vue'
import SavedIndicator from '../ui/SavedIndicator.vue'
import Tag from '../ui/Tag.vue'

/** The sticky bar under the top bar: where you are in the speaker list, what this speaker is, and the profile actions. */
const props = defineProps<{ slug: string }>()
const ctx = useSpeakerContext()
const store = useSpeakersStore()
const router = useRouter()

// the list gives the position and the neighbours; a page opened directly has not loaded it yet
onMounted(() => { if (!store.list.length) void store.load() })

const near = computed(() => store.neighbours(props.slug))
const pos = computed(() => store.position(props.slug))
const pct = computed(() => (pos.value.total ? Math.round((pos.value.index / pos.value.total) * 100) : 0))
const summary = computed(() => ctx.detail.value?.summary)
const design = computed(() => ctx.detail.value?.design ?? null)
const pickLabel = computed(() => (design.value?.pick ? shortId(design.value.pick) : 'pick'))
const saved = computed(() => ctx.detail.value?.profile?.saved)
const go = (slug: string | null) => slug && router?.push(`/speakers/${slug}`)

useWorkbenchAction('prev', () => go(near.value.prev))
useWorkbenchAction('next', () => go(near.value.next))
useWorkbenchAction('save', () => void ctx.saveProfile())
useWorkbenchAction('register', () => design.value?.pick && void ctx.registerPick())
</script>

<template>
  <div class="subbar">
    <component :is="near.prev ? 'RouterLink' : 'span'" v-bind="near.prev ? { to: `/speakers/${near.prev}` } : {}" data-prev class="nav" :class="{ off: !near.prev }" :aria-disabled="!near.prev">
      <Icon name="chev" :size="14" class="back" />Prev <Kbd>[</Kbd>
    </component>
    <div class="who">
      <h1 class="page-title name">{{ summary?.name }}</h1>
      <Tag :variant="summary?.origin === 'designed' ? 'designed' : 'real'">{{ summary?.origin }}</Tag>
      <span class="muted num small">{{ ctx.lines.value.length }} lines</span>
    </div>
    <component :is="near.next ? 'RouterLink' : 'span'" v-bind="near.next ? { to: `/speakers/${near.next}` } : {}" data-next class="nav" :class="{ off: !near.next }" :aria-disabled="!near.next">
      Next <Kbd>]</Kbd><Icon name="chev" :size="14" />
    </component>
    <div v-if="pos.total" class="progress hide-sm">
      <div class="lab"><span>Speaker {{ pos.index }} / {{ pos.total }}</span><span>{{ store.pickedCount }} picked</span></div>
      <div class="bar"><i :style="{ width: `${pct}%` }" /></div>
    </div>
    <div class="acts">
      <SavedIndicator v-if="saved" :ago="ago(saved)" />
      <span v-else class="muted small">No profile saved</span>
      <Btn size="sm" kbd="S" @click="ctx.saveProfile()">Save profile</Btn>
      <Btn size="sm" :disabled="!ctx.detail.value?.profile" title="Copy the saved profile to active.json" @click="ctx.setActive()">Set active</Btn>
      <Btn v-if="design" size="sm" variant="primary" data-register :disabled="!design.pick" title="Copy the picked candidate into the prompt bank so plan.py can use it" kbd="P" @click="ctx.registerPick()">Register {{ pickLabel }}</Btn>
    </div>
  </div>
</template>

<style scoped>
.subbar { position: sticky; top: var(--topbar-h); z-index: calc(var(--z-topbar) - 1); display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; margin: calc(-1 * var(--s-3)) calc(-1 * var(--s-4)) 0; padding: 10px var(--s-5); background: var(--bg); border-bottom: 1px solid var(--line); }
.nav { display: inline-flex; align-items: center; gap: 6px; min-height: 26px; padding: 0 var(--s-2); border-radius: var(--r-md); color: var(--text-2); font-size: var(--fs-sm); font-weight: 500; text-decoration: none; }
.nav:hover { background: var(--hover); color: var(--text); }
.off { color: var(--text-off); pointer-events: none; }
.back { transform: rotate(180deg); }
.who { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2); min-width: 0; }
.name { font-size: 20px; }
.small { font-size: var(--fs-sm); }
.progress { min-width: 160px; flex: 0 1 200px; display: flex; flex-direction: column; gap: 4px; }
.lab { display: flex; justify-content: space-between; font-size: var(--fs-xs); color: var(--text-3); }
.bar { height: 6px; border-radius: 3px; background: var(--n-4); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent); }
.acts { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; margin-left: auto; }
@media (max-width: 640px) { .subbar { position: static; padding: 8px var(--s-3); } }
</style>
