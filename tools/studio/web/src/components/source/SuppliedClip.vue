<script setup lang="ts">
import { ref } from 'vue'
import { useSpeakerContext } from '../../composables/useSpeakerContext'

const ctx = useSpeakerContext()
const wav = ref('')
const text = ref('')
function add() {
  if (!wav.value.trim()) return
  ctx.addSupplied(wav.value.trim(), text.value.trim())
  wav.value = text.value = ''
}
</script>

<template>
  <div class="supplied">
    <input v-model="wav" placeholder="other source wav, e.g. data/… .wav" />
    <input v-model="text" placeholder="its transcript" />
    <button @click="add">Add as source</button>
  </div>
</template>

<style scoped>
.supplied { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.supplied input { flex: 1; min-width: 200px; }
</style>
