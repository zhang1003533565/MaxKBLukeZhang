<template>
  <div class="open-api-document p-16-24">
    <div class="document-header flex-between mb-16">
      <div>
        <h2>{{ $t('views.system.knowledgeOpenAPIDocument.title') }}</h2>
        <p class="color-secondary mt-4">
          {{ $t('views.system.knowledgeOpenAPIDocument.description') }}
        </p>
      </div>
      <div class="document-actions flex align-center">
        <el-button type="primary" icon="Download" @click="downloadDocument">
          {{ $t('views.system.knowledgeOpenAPIDocument.download') }}
        </el-button>
      </div>
    </div>

    <el-card shadow="never" v-loading="loading">
      <el-alert
        v-if="errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
      >
        <el-button class="mt-8" size="small" @click="loadDocument">
          {{ $t('views.system.knowledgeOpenAPIDocument.retry') }}
        </el-button>
      </el-alert>
      <MdPreview
        v-else-if="markdownContent"
        editor-id="knowledge-open-api-document"
        :model-value="markdownContent"
        class="document-content"
      />
      <el-empty
        v-else-if="!loading"
        :description="$t('views.system.knowledgeOpenAPIDocument.empty')"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { t } from '@/locales'

const markdownContent = ref('')
const errorMessage = ref('')
const loading = ref(false)

const documentContentUrl = '/openapi/knowledge/docs/content'
const documentDownloadUrl = '/openapi/knowledge/docs/download'

async function loadDocument() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await fetch(documentContentUrl)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    markdownContent.value = await response.text()
  } catch {
    markdownContent.value = ''
    errorMessage.value = t('views.system.knowledgeOpenAPIDocument.loadFailed')
  } finally {
    loading.value = false
  }
}

function downloadDocument() {
  window.location.assign(documentDownloadUrl)
}

onMounted(loadDocument)
</script>

<style scoped lang="scss">
.open-api-document {
  height: 100%;
  overflow: auto;

  .document-header {
    gap: 16px;
  }

  .document-actions {
    flex-shrink: 0;
    gap: 8px;
  }

  .document-content {
    min-height: 480px;
    background: transparent;
  }

  :deep(.md-editor-preview-wrapper) {
    padding: 8px 16px 24px;
  }
}

@media (max-width: 720px) {
  .open-api-document {
    .document-header {
      align-items: flex-start;
      flex-direction: column;
    }

    .document-actions {
      flex-wrap: wrap;
    }

    :deep(.md-editor-preview-wrapper) {
      padding-right: 0;
      padding-left: 0;
    }
  }
}
</style>
