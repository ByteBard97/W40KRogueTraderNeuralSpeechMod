<script setup lang="ts">
// Only the dark tokens and base reset. The Studio's own shell brings a router, audio bar and top bar this page must not have.
import '../styles/tokens.css'
import '../styles/base.css'
</script>

<template>
  <div class="shell"><slot /></div>
</template>

<style scoped>
.shell { min-height: 100vh; background: var(--bg); }
</style>
