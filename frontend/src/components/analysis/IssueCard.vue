<template>
  <article class="issue-card">
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>
