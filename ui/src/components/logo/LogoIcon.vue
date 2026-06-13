<template>
  <img src="@/assets/logo/liuguang-kb-icon.svg" :height="height" alt="" />
</template>
<script setup lang="ts">
defineOptions({ name: 'LogoIcon' })

defineProps({
  height: {
    type: String,
    default: '36px',
  },
})
</script>
