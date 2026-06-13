<template>
  <MdEditor :language="language" noIconfont noPrettier v-bind="$attrs">
    <template #defFooters>
      <slot name="defFooters"> </slot>
    </template>
  </MdEditor>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MdEditor } from 'md-editor-v3'
import { getBrowserLang, normalizeLocale } from '@/locales/index'
import './assets/markdown-iconfont.js'
defineOptions({ name: 'MdEditor' })
const language = computed(() => normalizeLocale(localStorage.getItem('MaxKB-locale') || getBrowserLang()))
</script>
