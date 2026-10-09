<script setup lang="ts">
import ModelStatus from './ModelStatus.vue'
</script>

<template>
  <header class="bar">
    <h1>Voice Studio</h1>
    <nav class="nav"><RouterLink to="/speakers">Speakers</RouterLink><RouterLink to="/pools">Pools</RouterLink><RouterLink to="/fx">FX</RouterLink><RouterLink to="/matches">Matches</RouterLink></nav>
    <span class="spacer" />
    <ModelStatus />
  </header>
  <main class="main"><slot /></main>
</template>

<style>
:root { --bg: #14161a; --card: #1e2430; --line: #2c3444; --fg: #e8e8e8; --dim: #98a2b3; --ok: #3fb68b; --bad: #e5645b; --acc: #6aa5ff; color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; font: 14px system-ui, sans-serif; background: var(--bg); color: var(--fg); }
button, input, select, textarea { font: inherit; color: var(--fg); background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 5px 9px; }
button { cursor: pointer; }
button:disabled { opacity: 0.5; cursor: default; }
a { color: var(--acc); }
</style>

<style scoped>
.bar { position: sticky; top: 0; z-index: 5; display: flex; gap: 14px; align-items: center; padding: 8px 16px; background: var(--bg); border-bottom: 1px solid var(--line); }
h1 { font-size: 16px; margin: 0; }
.spacer { flex: 1; }
.nav { display: flex; gap: 14px; }
.main { padding: 12px 16px; }
</style>
