<template>
  <div class="knowledge-chat-test p-16-24">
    <div class="chat-shell">
      <aside v-loading="knowledgeLoading || modelLoading" class="chat-sidebar border-r">
        <div class="sidebar-header flex align-center mb-16">
          <AppIcon iconName="app-chat" class="mr-8 color-primary" />
          <h3>{{ $t('views.knowledge.chatTest.title') }}</h3>
        </div>

        <el-form label-position="top">
          <el-form-item :label="$t('views.knowledge.chatTest.knowledge')">
            <el-select
              v-model="form.knowledge_id_list"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              class="w-full"
              :placeholder="$t('views.knowledge.chatTest.knowledgePlaceholder')"
            >
              <el-option
                v-for="item in knowledgeOptions"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item :label="$t('views.knowledge.chatTest.model')">
            <el-select
              v-model="form.llm_model_id"
              filterable
              class="w-full"
              :placeholder="$t('views.knowledge.chatTest.modelPlaceholder')"
            >
              <el-option
                v-for="item in modelOptions"
                :key="item.id"
                :label="modelLabel(item)"
                :value="item.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item :label="$t('views.application.dialog.selectSearchMode')">
            <el-radio-group v-model="form.search_mode" class="mode-group">
              <el-radio-button label="embedding">
                {{ $t('views.application.dialog.vectorSearch') }}
              </el-radio-button>
              <el-radio-button label="keywords">
                {{ $t('views.application.dialog.fullTextSearch') }}
              </el-radio-button>
              <el-radio-button label="blend">
                {{ $t('views.application.dialog.hybridSearch') }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item :label="$t('views.application.dialog.topReferences')">
            <el-input-number v-model="form.top_number" :min="1" :max="20" class="w-full" />
          </el-form-item>

          <el-form-item :label="$t('views.application.dialog.similarityThreshold')">
            <el-input-number
              v-model="form.similarity"
              :min="0"
              :max="2"
              :step="0.01"
              :precision="2"
              class="w-full"
            />
          </el-form-item>
        </el-form>

        <el-button class="w-full" @click="clearMessages">
          {{ $t('views.knowledge.chatTest.clear') }}
        </el-button>
      </aside>

      <section class="chat-main">
        <el-scrollbar ref="scrollbarRef" class="messages-scroll">
          <div class="messages">
            <div
              v-for="message in messages"
              :key="message.id"
              class="message-row"
              :class="message.role"
            >
              <div class="message-bubble">
                <div class="message-content">{{ message.content }}</div>
                <div v-if="message.references?.length" class="reference-list">
                  <div
                    v-for="(item, index) in message.references"
                    :key="`${message.id}-${item.id || index}`"
                    class="reference-item border"
                  >
                    <div class="flex-between mb-6">
                      <div class="ellipsis">
                        <span class="bold">{{ item.knowledge_name }}</span>
                        <span class="color-secondary ml-8">{{ item.document_name }}</span>
                      </div>
                      <el-tag size="small" type="info">
                        {{ scoreText(item) }}
                      </el-tag>
                    </div>
                    <div class="reference-content">{{ item.content }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-scrollbar>

        <div class="chat-input border-t">
          <el-input
            ref="inputRef"
            v-model="question"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :placeholder="$t('views.knowledge.chatTest.inputPlaceholder')"
            @keydown.enter="sendMessage"
          />
          <el-button type="primary" :loading="loading" :disabled="!question.trim()" @click="sendMessage">
            {{ $t('common.send') }}
          </el-button>
        </div>
      </section>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { MsgWarning } from '@/utils/message'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { arraySort } from '@/utils/array'
import { t } from '@/locales'
import useStore from '@/stores'

type ChatMessage = {
  id: string
  role: 'assistant' | 'user'
  content: string
  references?: any[]
}

const loading = ref(false)
const knowledgeLoading = ref(false)
const modelLoading = ref(false)
const knowledgeOptions = ref<any[]>([])
const modelOptions = ref<any[]>([])
const messages = ref<ChatMessage[]>([])
const question = ref('')
const scrollbarRef = ref()
const inputRef = ref()
const { user } = useStore()

const form = reactive({
  knowledge_id_list: [] as string[],
  llm_model_id: '',
  top_number: 5,
  similarity: 0.6,
  search_mode: 'blend',
})

function createId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function scoreText(item: any) {
  return Number(item.comprehensive_score || item.similarity || 0).toFixed(3)
}

function modelLabel(item: any) {
  if (item.model_name && item.model_name !== item.name) {
    return `${item.name} (${item.model_name})`
  }
  return item.name
}

function normalizeModelList(data: any) {
  if (Array.isArray(data)) {
    return data
  }
  return [...(data?.shared_model || []), ...(data?.model || [])]
}

function scrollToBottom() {
  nextTick(() => {
    scrollbarRef.value?.setScrollTop?.(Number.MAX_SAFE_INTEGER)
  })
}

function resetGreeting() {
  messages.value = [
    {
      id: createId(),
      role: 'assistant',
      content: t('views.knowledge.chatTest.greeting'),
    },
  ]
}

function clearMessages() {
  resetGreeting()
  question.value = ''
  nextTick(() => inputRef.value?.focus?.())
}

function buildAssistantContent(list: any[]) {
  if (!list.length) {
    return t('views.knowledge.chatTest.noReference')
  }
  return t('views.knowledge.chatTest.referenceSummary', { count: list.length })
}

function sendMessage(event?: KeyboardEvent | MouseEvent) {
  if (event) {
    if (event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) {
      return
    }
    event.preventDefault()
  }
  const text = question.value.trim()
  if (!form.knowledge_id_list.length) {
    MsgWarning(t('views.knowledge.chatTest.knowledgeRequired'))
    return
  }
  if (!form.llm_model_id) {
    MsgWarning(t('views.knowledge.chatTest.modelRequired'))
    return
  }
  if (!text || loading.value) return

  messages.value.push({ id: createId(), role: 'user', content: text })
  question.value = ''
  scrollToBottom()
  loading.value = true
  loadSharedApi({ type: 'knowledge', systemType: 'workspace' })
    .postKnowledgeChatTest(
      {
        ...form,
        query_text: text,
      },
      loading,
    )
    .then((res: any) => {
      const references = arraySort(res.data?.references || [], 'comprehensive_score', true)
      messages.value.push({
        id: createId(),
        role: 'assistant',
        content: res.data?.answer || buildAssistantContent(references),
        references,
      })
      scrollToBottom()
    })
}

function loadKnowledgeList() {
  loadSharedApi({ type: 'knowledge', systemType: 'workspace' })
    .getKnowledgeListPage(
      { current_page: 1, page_size: 1000 },
      { folder_id: user.getWorkspaceId(), scope: 'WORKSPACE' },
      knowledgeLoading,
    )
    .then((res: any) => {
      knowledgeOptions.value = res.data?.records || []
      form.knowledge_id_list = knowledgeOptions.value.map((item) => item.id)
    })
}

function loadModelList() {
  loadSharedApi({ type: 'knowledge', systemType: 'workspace' })
    .getKnowledgeModel(modelLoading)
    .then((res: any) => {
      modelOptions.value = normalizeModelList(res.data)
      if (modelOptions.value.length === 1) {
        form.llm_model_id = modelOptions.value[0].id
      }
    })
}

onMounted(() => {
  resetGreeting()
  loadKnowledgeList()
  loadModelList()
})
</script>

<style lang="scss" scoped>
.knowledge-chat-test {
  height: calc(100vh - var(--app-header-height));
  box-sizing: border-box;
}

.chat-shell {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  height: 100%;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
  background: #ffffff;
}

.chat-sidebar {
  padding: 20px;
  background: var(--app-layout-bg-color);
  overflow: auto;
}

.mode-group {
  width: 100%;
  :deep(.el-radio-button) {
    width: 33.333%;
  }
  :deep(.el-radio-button__inner) {
    width: 100%;
  }
}

.chat-main {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  min-width: 0;
}

.messages-scroll {
  height: 100%;
}

.messages {
  padding: 24px;
}

.message-row {
  display: flex;
  margin-bottom: 18px;

  &.user {
    justify-content: flex-end;
    .message-bubble {
      background: var(--el-color-primary);
      color: #ffffff;
      max-width: min(680px, 76%);
    }
  }

  &.assistant {
    justify-content: flex-start;
    .message-bubble {
      background: var(--app-layout-bg-color);
      color: var(--el-text-color-primary);
      max-width: min(820px, 82%);
    }
  }
}

.message-bubble {
  border-radius: 8px;
  padding: 12px 14px;
}

.message-content {
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.reference-list {
  margin-top: 12px;
}

.reference-item {
  padding: 12px;
  border-radius: 6px;
  background: #ffffff;
  color: var(--el-text-color-primary);

  & + .reference-item {
    margin-top: 8px;
  }
}

.reference-content {
  line-height: 1.7;
  max-height: 108px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-input {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  padding: 14px 16px;
  background: #ffffff;
}
</style>
