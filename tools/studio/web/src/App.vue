<script setup lang="ts">
import AppShell from './components/shared/AppShell.vue'
</script>

<template>
  <AppShell>
    <RouterView v-slot="{ Component, route }">
      <component :is="Component" :key="route.fullPath" />
    </RouterView>
  </AppShell>
</template>
