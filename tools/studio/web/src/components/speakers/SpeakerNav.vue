<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useSpeakersStore } from '../../stores/speakers'
import RegisterAllButton from './RegisterAllButton.vue'

const props = defineProps<{ slug: string }>()
const store = useSpeakersStore()
onMounted(() => { if (!store.list.length) void store.load() })

const near = computed(() => store.neighbours(props.slug))
const pos = computed(() => store.position(props.slug))
</script>

<template>
  <nav class="nav">
    <RouterLink v-if="near.prev" data-prev :to="`/speakers/${near.prev}`">← prev</RouterLink>
    <span v-else data-prev class="off">← prev</span>
    <RouterLink v-if="near.next" data-next :to="`/speakers/${near.next}`">next →</RouterLink>
    <span v-else data-next class="off">next →</span>
    <span class="dim">{{ pos.index }} / {{ pos.total }}, {{ store.pickedCount }} picked</span>
    <RegisterAllButton />
  </nav>
</template>

<style scoped>
.nav { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.off { color: var(--dim); }
.dim { color: var(--dim); font-size: 12px; }
</style>
