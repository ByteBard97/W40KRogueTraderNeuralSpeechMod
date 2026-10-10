<script setup lang="ts">
import { useAudioKeys } from '../../composables/useAudioKeys'
import AudioBar from '../ui/AudioBar.vue'
import ShortcutOverlay from '../ui/ShortcutOverlay.vue'
import ToastStack from '../ui/ToastStack.vue'
import TopBar from './TopBar.vue'

useAudioKeys()
</script>

<template>
  <div class="app">
    <TopBar />
    <main class="main"><slot /></main>
    <AudioBar />
    <ToastStack />
    <ShortcutOverlay />
  </div>
</template>

<style scoped>
.app { min-height: 100vh; display: flex; flex-direction: column; background: var(--bg); padding-bottom: var(--bar-h); }
.main { padding: var(--s-3) var(--s-4); flex: 1 1 auto; }
</style>
