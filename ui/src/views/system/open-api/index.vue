<template>
  <div class="knowledge-open-api p-16-24">
    <div class="flex-between mb-16">
      <div>
        <h2>{{ $t('views.system.knowledgeOpenAPI.title') }}</h2>
        <p class="color-secondary mt-4">
          {{ $t('views.system.knowledgeOpenAPI.description') }}
        </p>
      </div>
      <el-button type="primary" icon="Plus" @click="createKeyHandle" :loading="loading">
        {{ $t('views.system.knowledgeOpenAPI.createKey') }}
      </el-button>
    </div>

    <el-card class="mb-16" shadow="never">
      <template #header>
        <div class="flex-between">
          <span>{{ $t('views.system.knowledgeOpenAPI.accessConfig') }}</span>
          <el-tag>{{ currentWorkspaceName }}</el-tag>
        </div>
      </template>
      <div class="form-line">
        <span class="form-label">{{ $t('views.system.knowledgeOpenAPI.baseUrl') }}</span>
        <el-input :model-value="baseUrl" readonly>
          <template #append>
            <el-button @click="copyClick(baseUrl)">
              {{ $t('common.copy') }}
            </el-button>
          </template>
        </el-input>
      </div>
      <el-table class="mt-16" :data="keyList" border v-loading="loading">
        <el-table-column prop="name" :label="$t('common.name')" min-width="140" />
        <el-table-column
          prop="secret_key"
          :label="$t('views.system.knowledgeOpenAPI.apiKey')"
          min-width="260"
          show-overflow-tooltip
        />
        <el-table-column
          prop="workspace_name"
          :label="$t('views.workspace.title')"
          min-width="140"
        />
        <el-table-column :label="$t('common.status.label')" width="110">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="updateKeyStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column :label="$t('common.operation')" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="copyClick(row.secret_key)">
              {{ $t('common.copy') }}
            </el-button>
            <el-button link type="danger" @click="deleteKeyHandle(row.id)">
              {{ $t('common.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <div class="content-grid">
      <el-card shadow="never">
        <template #header>
          <span>{{ $t('views.system.knowledgeOpenAPI.docTitle') }}</span>
        </template>
        <el-scrollbar height="520px">
          <div
            v-for="endpoint in endpoints"
            :key="endpoint.path + endpoint.method"
            class="endpoint-item"
          >
            <div
              class="endpoint-item__head flex align-center mb-8"
              :class="{ active: testType === endpoint.value }"
            >
              <el-tag :type="getMethodTagType(endpoint.method)" class="mr-8">
                {{ endpoint.method }}
              </el-tag>
              <code>{{ endpoint.path }}</code>
            </div>
            <p class="color-secondary">{{ endpoint.description }}</p>
            <pre>{{ endpoint.example }}</pre>
            <el-button class="mt-8" size="small" @click="selectEndpoint(endpoint.value)">
              {{ $t('views.system.knowledgeOpenAPI.testThisEndpoint') }}
            </el-button>
          </div>
        </el-scrollbar>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <span>{{ $t('views.system.knowledgeOpenAPI.testTitle') }}</span>
        </template>
        <div class="selected-endpoint mb-16">
          <el-tag :type="getMethodTagType(selectedEndpoint.method)" class="mr-8">
            {{ selectedEndpoint.method }}
          </el-tag>
          <code>{{ buildTestUrl() }}</code>
          <p class="color-secondary mt-8">
            {{ $t('views.system.knowledgeOpenAPI.singleTestTip') }}
          </p>
        </div>
        <el-form label-position="top">
          <el-form-item :label="$t('views.system.knowledgeOpenAPI.apiKey')">
            <el-select
              v-model="selectedKey"
              class="w-full"
              :placeholder="$t('views.system.knowledgeOpenAPI.selectKey')"
            >
              <el-option
                v-for="item in keyList"
                :key="item.id"
                :label="item.name || item.secret_key"
                :value="item.secret_key"
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('views.system.knowledgeOpenAPI.endpoint')">
            <el-select v-model="testType" class="w-full">
              <el-option
                v-for="item in testTypeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item
            v-if="['knowledgeDetail', 'documents', 'paragraphs', 'upload'].includes(testType)"
            :label="$t('views.system.knowledgeOpenAPI.knowledgeId')"
          >
            <el-input v-model="form.knowledgeId" clearable />
          </el-form-item>
          <el-form-item
            v-if="testType === 'paragraphs'"
            :label="$t('views.system.knowledgeOpenAPI.documentId')"
          >
            <el-input v-model="form.documentId" clearable />
          </el-form-item>
          <el-form-item
            v-if="testType === 'hitTest'"
            :label="$t('views.system.knowledgeOpenAPI.knowledgeIds')"
          >
            <el-input v-model="form.knowledgeIds" clearable />
          </el-form-item>
          <el-form-item
            v-if="testType === 'hitTest'"
            :label="$t('views.system.knowledgeOpenAPI.queryText')"
          >
            <el-input v-model="form.queryText" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item
            v-if="testType === 'upload'"
            :label="$t('views.system.knowledgeOpenAPI.file')"
          >
            <el-upload :auto-upload="false" :limit="1" :on-change="setUploadFile">
              <el-button>{{ $t('views.system.knowledgeOpenAPI.selectFile') }}</el-button>
            </el-upload>
          </el-form-item>
        </el-form>
        <el-button class="w-full" type="primary" @click="testAPI" :loading="testLoading">
          {{ $t('views.system.knowledgeOpenAPI.sendTest') }}
        </el-button>
        <pre class="result-box">{{ testResult }}</pre>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { TagProps } from 'element-plus'
import { t } from '@/locales'
import useStore from '@/stores'
import OpenAPI from '@/api/system/open-api'
import { copyClick } from '@/utils/clipboard'
import { MsgConfirm, MsgError, MsgSuccess } from '@/utils/message'

const { user } = useStore()
const loading = ref(false)
const testLoading = ref(false)
interface OpenAPIKeyItem {
  id: string
  name: string
  secret_key: string
  workspace_name: string
  is_active: boolean
}
type EndpointMethod = 'GET' | 'POST'
type TestType = 'knowledges' | 'knowledgeDetail' | 'documents' | 'paragraphs' | 'hitTest' | 'upload'
interface EndpointItem {
  value: TestType
  method: EndpointMethod
  path: string
  description: string
  example: string
}

const keyList = ref<OpenAPIKeyItem[]>([])
const selectedKey = ref('')
const testType = ref<TestType>('knowledges')
const testResult = ref('')
const uploadFile = ref<File>()

const form = reactive({
  knowledgeId: '',
  documentId: '',
  knowledgeIds: '',
  queryText: '',
})

const workspaceId = computed(() => user.getWorkspaceId() || 'default')
const currentWorkspaceName = computed(() => {
  return user.workspace_list.find((item) => item.id === workspaceId.value)?.name || workspaceId.value
})
const baseUrl = computed(() => {
  return `${window.location.origin}/openapi/knowledge/v1/workspaces/${workspaceId.value}`
})

const endpoints = computed<EndpointItem[]>(() => [
  {
    value: 'knowledges',
    method: 'GET',
    path: `${baseUrl.value}/knowledges`,
    description: t('views.system.knowledgeOpenAPI.docs.knowledges'),
    example: `curl -H "Authorization: Bearer ${selectedKey.value || '<api_key>'}" "${baseUrl.value}/knowledges?current_page=1&page_size=20"`,
  },
  {
    value: 'knowledgeDetail',
    method: 'GET',
    path: `${baseUrl.value}/knowledges/{knowledge_id}`,
    description: t('views.system.knowledgeOpenAPI.docs.knowledgeDetail'),
    example: `curl -H "Authorization: Bearer ${selectedKey.value || '<api_key>'}" "${baseUrl.value}/knowledges/{knowledge_id}"`,
  },
  {
    value: 'documents',
    method: 'GET',
    path: `${baseUrl.value}/knowledges/{knowledge_id}/documents`,
    description: t('views.system.knowledgeOpenAPI.docs.documents'),
    example: `curl -H "Authorization: Bearer ${selectedKey.value || '<api_key>'}" "${baseUrl.value}/knowledges/{knowledge_id}/documents"`,
  },
  {
    value: 'upload',
    method: 'POST',
    path: `${baseUrl.value}/knowledges/{knowledge_id}/documents/upload`,
    description: t('views.system.knowledgeOpenAPI.docs.upload'),
    example: `curl -X POST -H "Authorization: Bearer ${selectedKey.value || '<api_key>'}" -F "file=@demo.docx" "${baseUrl.value}/knowledges/{knowledge_id}/documents/upload"`,
  },
  {
    value: 'paragraphs',
    method: 'GET',
    path: `${baseUrl.value}/knowledges/{knowledge_id}/documents/{document_id}/paragraphs`,
    description: t('views.system.knowledgeOpenAPI.docs.paragraphs'),
    example: `curl -H "Authorization: Bearer ${selectedKey.value || '<api_key>'}" "${baseUrl.value}/knowledges/{knowledge_id}/documents/{document_id}/paragraphs"`,
  },
  {
    value: 'hitTest',
    method: 'POST',
    path: `${baseUrl.value}/hit-test`,
    description: t('views.system.knowledgeOpenAPI.docs.hitTest'),
    example: `curl -X POST -H "Authorization: Bearer ${selectedKey.value || '<api_key>'}" -H "Content-Type: application/json" -d '{"knowledge_id_list":["{knowledge_id}"],"query_text":"test"}' "${baseUrl.value}/hit-test"`,
  },
])

const testTypeOptions = computed(() => [
  { label: t('views.system.knowledgeOpenAPI.testTypes.knowledges'), value: 'knowledges' },
  { label: t('views.system.knowledgeOpenAPI.testTypes.knowledgeDetail'), value: 'knowledgeDetail' },
  { label: t('views.system.knowledgeOpenAPI.testTypes.documents'), value: 'documents' },
  { label: t('views.system.knowledgeOpenAPI.testTypes.paragraphs'), value: 'paragraphs' },
  { label: t('views.system.knowledgeOpenAPI.testTypes.hitTest'), value: 'hitTest' },
  { label: t('views.system.knowledgeOpenAPI.testTypes.upload'), value: 'upload' },
])

const selectedEndpoint = computed(() => {
  return endpoints.value.find((endpoint) => endpoint.value === testType.value) || endpoints.value[0]
})

function getMethodTagType(method: EndpointMethod): TagProps['type'] {
  return method === 'GET' ? 'success' : 'primary'
}

function selectEndpoint(value: TestType) {
  testType.value = value
  testResult.value = ''
}

function syncSelectedKey() {
  if (!selectedKey.value && keyList.value.length > 0) {
    selectedKey.value = keyList.value[0].secret_key
  }
}

function loadKeys() {
  OpenAPI.getKeyList({ workspace_id: workspaceId.value }, loading).then((res) => {
    keyList.value = res.data || []
    syncSelectedKey()
  })
}

function createKeyHandle() {
  OpenAPI.createKey(
    {
      name: `${currentWorkspaceName.value} ${t('views.system.knowledgeOpenAPI.apiKey')}`,
      workspace_id: workspaceId.value,
    },
    loading,
  ).then((res) => {
    MsgSuccess(t('common.createSuccess'))
    selectedKey.value = res.data.secret_key
    loadKeys()
  })
}

function updateKeyStatus(row: OpenAPIKeyItem) {
  OpenAPI.updateKey(row.id, { is_active: row.is_active }, loading).then(() => {
    MsgSuccess(t('common.saveSuccess'))
  })
}

function deleteKeyHandle(keyId: string) {
  MsgConfirm(t('common.tip'), t('views.system.knowledgeOpenAPI.deleteConfirm')).then(() => {
    OpenAPI.deleteKey(keyId, loading).then(() => {
      MsgSuccess(t('common.deleteSuccess'))
      if (selectedKey.value === keyList.value.find((item) => item.id === keyId)?.secret_key) {
        selectedKey.value = ''
      }
      loadKeys()
    })
  })
}

function setUploadFile(file: { raw?: File }) {
  uploadFile.value = file.raw
}

function requireKey() {
  if (!selectedKey.value) {
    MsgError(t('views.system.knowledgeOpenAPI.selectKey'))
    return false
  }
  return true
}

function testAPI() {
  if (!requireKey()) {
    return
  }
  if (['knowledgeDetail', 'documents', 'paragraphs', 'upload'].includes(testType.value) && !form.knowledgeId) {
    MsgError(t('views.system.knowledgeOpenAPI.knowledgeIdRequired'))
    return
  }
  if (testType.value === 'paragraphs' && !form.documentId) {
    MsgError(t('views.system.knowledgeOpenAPI.documentIdRequired'))
    return
  }
  if (testType.value === 'hitTest' && (!form.knowledgeIds || !form.queryText)) {
    MsgError(t('views.system.knowledgeOpenAPI.hitTestRequired'))
    return
  }
  if (testType.value === 'upload' && !uploadFile.value) {
    MsgError(t('views.system.knowledgeOpenAPI.selectFile'))
    return
  }
  testLoading.value = true
  const url = buildTestUrl()
  const request =
    testType.value === 'hitTest'
      ? OpenAPI.callOpenAPI(url, selectedKey.value, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            knowledge_id_list: form.knowledgeIds.split(',').map((item) => item.trim()).filter(Boolean),
            query_text: form.queryText,
            top_number: 5,
            similarity: 0.6,
            search_mode: 'blend',
          }),
        })
      : testType.value === 'upload'
        ? uploadTest(url)
        : OpenAPI.callOpenAPI(url, selectedKey.value)
  request
    .then((res) => {
      testResult.value = JSON.stringify(res, null, 2)
    })
    .catch((error) => {
      testResult.value = JSON.stringify(error, null, 2)
    })
    .finally(() => {
      testLoading.value = false
    })
}

function uploadTest(url: string) {
  const formData = new FormData()
  if (uploadFile.value) {
    formData.append('file', uploadFile.value)
  }
  return OpenAPI.uploadDocument(url, selectedKey.value, formData)
}

function buildTestUrl() {
  if (testType.value === 'knowledgeDetail') {
    return `${baseUrl.value}/knowledges/${form.knowledgeId || '{knowledge_id}'}`
  }
  if (testType.value === 'documents') {
    return `${baseUrl.value}/knowledges/${form.knowledgeId || '{knowledge_id}'}/documents?current_page=1&page_size=10`
  }
  if (testType.value === 'paragraphs') {
    return `${baseUrl.value}/knowledges/${form.knowledgeId || '{knowledge_id}'}/documents/${form.documentId || '{document_id}'}/paragraphs?current_page=1&page_size=10`
  }
  if (testType.value === 'hitTest') {
    return `${baseUrl.value}/hit-test`
  }
  if (testType.value === 'upload') {
    return `${baseUrl.value}/knowledges/${form.knowledgeId || '{knowledge_id}'}/documents/upload`
  }
  return `${baseUrl.value}/knowledges?current_page=1&page_size=10`
}

watch(workspaceId, () => {
  selectedKey.value = ''
  loadKeys()
})

onMounted(loadKeys)
</script>

<style scoped lang="scss">
.knowledge-open-api {
  .form-line {
    display: grid;
    grid-template-columns: 120px minmax(0, 1fr);
    gap: 12px;
    align-items: center;
  }

  .form-label {
    color: var(--el-text-color-regular);
  }

  .content-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(360px, 0.9fr);
    gap: 16px;
  }

  .endpoint-item {
    padding: 12px 0;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  .endpoint-item__head {
    padding: 6px 8px;
    border-radius: 4px;

    &.active {
      background: var(--el-color-primary-light-9);
    }
  }

  .selected-endpoint {
    padding: 12px;
    border: 1px solid var(--el-border-color-lighter);
    background: var(--el-fill-color-light);
  }

  code,
  pre {
    white-space: pre-wrap;
    word-break: break-all;
  }

  pre {
    margin: 10px 0 0;
    padding: 12px;
    background: var(--el-fill-color-light);
    border: 1px solid var(--el-border-color-lighter);
  }

  .result-box {
    min-height: 180px;
    max-height: 360px;
    overflow: auto;
  }

  @media (max-width: 1100px) {
    .content-grid,
    .form-line {
      grid-template-columns: 1fr;
    }
  }
}
</style>
