<template>
  <img v-if="theme.themeInfo?.loginLogo" :src="fileURL" alt="" height="45px" class="mr-8" />
  <span v-else class="default-logo-full" :style="{ height }">
    <img src="@/assets/logo/liuguang-kb-icon.svg" alt="" class="default-logo-icon" />
    <span class="default-logo-title">流光知识库</span>
  </span>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import useStore from '@/stores'
defineOptions({ name: 'LogoFull' })

defineProps({
  height: {
    type: String,
    default: '36px',
  },
})
const { theme } = useStore()

const fileURL = computed(() => {
  if (theme.themeInfo) {
    if (typeof theme.themeInfo?.loginLogo === 'string') {
      return theme.themeInfo?.loginLogo
    } else {
      return URL.createObjectURL(theme.themeInfo?.loginLogo)
    }
  } else {
    return ''
  }
})
</script>
<style lang="scss" scoped>
.default-logo-full {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  line-height: 1;
}

.default-logo-icon {
  display: block;
  width: auto;
  height: 100%;
  flex: 0 0 auto;
}

.default-logo-title {
  color: #111827;
  font-size: 20px;
  font-weight: 750;
  letter-spacing: 0;
  white-space: nowrap;
}
</style>
