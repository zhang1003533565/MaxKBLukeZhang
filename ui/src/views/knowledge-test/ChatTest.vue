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

          <el-form-item :label="$t('views.knowledge.chatTest.responseMode')">
            <el-radio-group v-model="form.response_mode" class="response-mode-group">
              <el-radio-button label="stream">
                {{ $t('views.knowledge.chatTest.streamMode') }}
              </el-radio-button>
              <el-radio-button label="normal">
                {{ $t('views.knowledge.chatTest.normalMode') }}
              </el-radio-button>
            </el-radio-group>
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
                <template v-if="message.role === 'assistant'">
                  <div v-if="message.referencesLoaded" class="reference-panel border">
                    <div class="reference-panel-header">
                      <span>{{ $t('views.knowledge.chatTest.hitReferences') }}</span>
                      <el-tag size="small" type="info">
                        {{ $t('views.knowledge.chatTest.hitCount', { count: message.references?.length || 0 }) }}
                      </el-tag>
                    </div>
                    <el-empty
                      v-if="!message.references?.length"
                      :description="$t('views.knowledge.chatTest.noReferenceShort')"
                      :image-size="56"
                    />
                    <div v-else class="reference-list">
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
                        <MdPreview
                          editorId="preview-only"
                          :modelValue="item.content || ''"
                          class="reference-content maxkb-md"
                          noImgZoomIn
                        />
                      </div>
                    </div>
                  </div>
                  <div v-if="message.content" class="message-content">{{ message.content }}</div>
                  <div v-else-if="message.loading" class="typing-indicator">
                    <span />
                    <span />
                    <span />
                  </div>
                </template>
                <div v-else class="message-content">{{ message.content }}</div>
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
import { MsgError, MsgWarning } from '@/utils/message'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { arraySort } from '@/utils/array'
import { t } from '@/locales'
import useStore from '@/stores'

type ChatMessage = {
  id: string
  role: 'assistant' | 'user'
  content: string
  references?: any[]
  referencesLoaded?: boolean
  loading?: boolean
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
  response_mode: 'stream',
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

function buildEmptyAnswerContent() {
  return t('views.knowledge.chatTest.emptyAnswer')
}

type StreamEvent = {
  event: string
  data: string
}

function parseStreamEvents(buffer: string) {
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n')
  const rest = blocks.pop() || ''
  const events = blocks
    .map((block) => {
      const event: StreamEvent = { event: 'message', data: '' }
      block.split('\n').forEach((line) => {
        if (line.startsWith('event:')) {
          event.event = line.slice(6).trim()
        }
        if (line.startsWith('data:')) {
          event.data += line.slice(5).trim()
        }
      })
      return event
    })
    .filter((item) => item.data)
  return { events, rest }
}

function readStreamData(data: string) {
  try {
    return JSON.parse(data)
  } catch {
    return data
  }
}

function buildChatPayload(text: string) {
  return {
    knowledge_id_list: form.knowledge_id_list,
    llm_model_id: form.llm_model_id,
    top_number: form.top_number,
    similarity: form.similarity,
    search_mode: form.search_mode,
    query_text: text,
  }
}

function updateAssistantMessage(index: number, values: Partial<ChatMessage>) {
  messages.value[index] = {
    ...messages.value[index],
    ...values,
  }
}

function updateAssistantReferences(index: number, references: any[]) {
  updateAssistantMessage(index, {
    references,
    referencesLoaded: true,
  })
}

function updateAssistantContent(index: number, content: string) {
  updateAssistantMessage(index, {
    content,
  })
}

function appendAssistantContent(index: number, content: string) {
  updateAssistantContent(index, `${messages.value[index].content}${content}`)
}

function finishAssistantLoading(index: number) {
  updateAssistantMessage(index, {
    loading: false,
  })
}

async function sendNormalMessage(payload: ReturnType<typeof buildChatPayload>, assistantIndex: number) {
  const res = await loadSharedApi({ type: 'knowledge', systemType: 'workspace' })
    .postKnowledgeChatTest(payload)
  const references = Array.isArray(res.data?.references)
    ? arraySort(res.data.references, 'comprehensive_score', true)
    : []
  updateAssistantMessage(assistantIndex, {
    content: res.data?.answer || buildEmptyAnswerContent(),
    references,
    referencesLoaded: true,
    loading: false,
  })
}

async function sendStreamMessage(payload: ReturnType<typeof buildChatPayload>, assistantIndex: number) {
  const response = await loadSharedApi({ type: 'knowledge', systemType: 'workspace' })
    .postKnowledgeChatTestStream(payload)
  if (!response.ok || !response.body) {
    throw new Error(await response.text())
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let hasAnswer = false

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parsed = parseStreamEvents(buffer)
    buffer = parsed.rest
    parsed.events.forEach((streamEvent) => {
      const data = readStreamData(streamEvent.data)
      if (streamEvent.event === 'references') {
        const references = Array.isArray(data)
          ? arraySort(data, 'comprehensive_score', true)
          : []
        updateAssistantReferences(assistantIndex, references)
      }
      if (streamEvent.event === 'answer') {
        if (!hasAnswer) {
          updateAssistantMessage(assistantIndex, {
            content: '',
            loading: false,
          })
          hasAnswer = true
        }
        appendAssistantContent(assistantIndex, String(data))
      }
      if (streamEvent.event === 'error') {
        throw new Error(String(data))
      }
    })
  }

  const parsed = parseStreamEvents(buffer)
  parsed.events.forEach((streamEvent) => {
    const data = readStreamData(streamEvent.data)
    if (streamEvent.event === 'answer') {
      if (!hasAnswer) {
        updateAssistantMessage(assistantIndex, {
          content: '',
          loading: false,
        })
        hasAnswer = true
      }
      appendAssistantContent(assistantIndex, String(data))
    }
  })
  if (!hasAnswer) {
    updateAssistantContent(assistantIndex, buildEmptyAnswerContent())
  }
  finishAssistantLoading(assistantIndex)
}

async function sendMessage(event?: KeyboardEvent | MouseEvent) {
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
  const assistantIndex = messages.value.push({
    id: createId(),
    role: 'assistant',
    content: '',
    references: [],
    referencesLoaded: false,
    loading: true,
  }) - 1
  question.value = ''
  scrollToBottom()
  loading.value = true
  try {
    const payload = buildChatPayload(text)
    if (form.response_mode === 'stream') {
      await sendStreamMessage(payload, assistantIndex)
    } else {
      await sendNormalMessage(payload, assistantIndex)
    }
  } catch (error: any) {
    const message = error?.message || String(error)
    updateAssistantMessage(assistantIndex, {
      content: message,
      loading: false,
    })
    MsgError(message)
  } finally {
    finishAssistantLoading(assistantIndex)
    loading.value = false
  }
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
  display: flex;
  height: calc(100vh - var(--app-header-height));
  min-height: 0;
  box-sizing: border-box;
  overflow: hidden;
}

.chat-shell {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  flex: 1;
  height: 100%;
  min-height: 0;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
  background: #ffffff;
}

.chat-sidebar {
  padding: 20px;
  background: var(--app-layout-bg-color);
  overflow: auto;
  min-height: 0;
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

.response-mode-group {
  width: 100%;
  :deep(.el-radio-button) {
    width: 50%;
  }
  :deep(.el-radio-button__inner) {
    width: 100%;
  }
}

.chat-main {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  height: 100%;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.messages-scroll {
  height: 100%;
  min-height: 0;
}

.messages {
  padding: 24px;
  min-height: 100%;
  box-sizing: border-box;
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

  .reference-panel + & {
    margin-top: 12px;
  }
}

.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 20px;

  .reference-panel + & {
    margin-top: 12px;
  }

  span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--el-text-color-secondary);
    animation: typing-bounce 1.2s infinite ease-in-out;

    &:nth-child(2) {
      animation-delay: 0.16s;
    }

    &:nth-child(3) {
      animation-delay: 0.32s;
    }
  }
}

@keyframes typing-bounce {
  0%,
  80%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }

  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

.reference-panel {
  width: min(760px, 100%);
  padding: 10px;
  border-radius: 6px;
  background: #ffffff;
}

.reference-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.reference-list {
  max-height: 220px;
  overflow: auto;
}

.reference-item {
  padding: 12px;
  border-radius: 6px;
  background: var(--app-layout-bg-color);
  color: var(--el-text-color-primary);

  & + .reference-item {
    margin-top: 8px;
  }
}

.reference-content {
  line-height: 1.7;
  max-height: 160px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;

  :deep(.md-editor-preview-wrapper) {
    padding: 0;
  }

  :deep(img) {
    max-width: 100%;
    max-height: 120px;
    border-radius: 6px;
    object-fit: contain;
  }
}

.chat-input {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  padding: 14px 16px;
  background: #ffffff;
  min-height: 62px;
  box-sizing: border-box;
}
</style>
