<template>
  <MdPreview :language="language" noIconfont noPrettier :codeFoldable="false" v-bind="$attrs" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MdPreview } from 'md-editor-v3'
import { getBrowserLang, normalizeLocale } from '@/locales/index'
import useStore from '@/stores'
defineOptions({ name: 'MdPreview' })

const emit = defineEmits(['clickPreview'])

const { user } = useStore()
const language = computed(() => normalizeLocale(user.getLanguage() || getBrowserLang()))
</script>

<style lang="scss" scoped>
:deep(audio) {
  width: 300px;
  height: 43px;
}
</style>
