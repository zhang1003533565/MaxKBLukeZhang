<template>
  <el-dialog v-model="visible" :title="$t('views.document.quality.dialogTitle')" width="900px">
    <div v-if="!taskId">
      <div class="mb-8">{{ $t('views.document.quality.modelLabel') }}</div>
      <ModelSelect
        v-model="modelId"
        :options="modelOptions"
        :model-type="'LLM'"
        showFooter
        @submitModel="loadModels"
      />
    </div>
    <div v-else-if="status !== 'completed'">
      <el-alert
        v-if="status === 'failed'"
        type="error"
        :closable="false"
        class="mb-16"
        :title="message || $t('views.document.quality.failed')"
      />
      <div class="flex-between mb-8">
        <span>{{ message }}</span><span>{{ progress }}%</span>
      </div>
      <el-progress :percentage="progress" />
      <div class="text-right mt-16">
        <el-button v-if="activeTask" type="danger" plain :loading="cancelling" @click="cancelTask">
          {{ $t('views.document.quality.cancel') }}
        </el-button>
        <el-button v-else @click="resetTask">{{ $t('views.document.quality.retry') }}</el-button>
      </div>
    </div>
    <div v-else>
      <el-alert
        type="success"
        :closable="false"
        class="mb-16"
        :title="$t('views.document.quality.reportTitle')"
        :description="reportText"
      />
      <el-row :gutter="16">
        <el-col :span="12">
          <h4>{{ $t('views.document.quality.before') }}</h4>
          <el-scrollbar height="420px">
            <el-card v-for="(item, index) in result.before" :key="index" shadow="never" class="mb-8">
              <strong>{{ item.title }}</strong>
              <div class="mt-8 pre-wrap">{{ item.content }}</div>
            </el-card>
          </el-scrollbar>
        </el-col>
        <el-col :span="12">
          <h4>{{ $t('views.document.quality.after') }}</h4>
          <el-scrollbar height="420px">
            <el-card v-for="(item, index) in result.after" :key="index" shadow="never" class="mb-8">
              <strong>{{ item.title }}</strong>
              <div class="mt-8 pre-wrap">{{ item.content }}</div>
            </el-card>
          </el-scrollbar>
        </el-col>
      </el-row>
    </div>
    <template #footer>
      <el-button @click="visible = false">{{ $t('common.cancel') }}</el-button>
      <el-button v-if="!taskId" type="primary" :disabled="!modelId" :loading="starting" @click="startTask">
        {{ $t('views.document.quality.start') }}
      </el-button>
      <el-button v-if="status === 'completed'" type="primary" :loading="applying" @click="applyTask">
        {{ $t('views.document.quality.apply') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { groupBy } from 'lodash'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { t } from '@/locales'

const props = defineProps<{ knowledgeId: string; documentId: string }>()
const emit = defineEmits<{ refresh: [] }>()
const visible = ref(false)
const modelId = ref('')
const modelOptions = ref<any>({})
const taskId = ref('')
const status = ref('')
const progress = ref(0)
const message = ref('')
const result = ref<any>({ before: [], after: [], report: {} })
const starting = ref(false)
const cancelling = ref(false)
const applying = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
let pollingFailures = 0
let pollingGeneration = 0

const api = () => loadSharedApi({ type: 'document', systemType: 'workspace' })
const reportText = computed(() => t('views.document.quality.report', result.value.report || {}))
const activeTask = computed(() => ['queued', 'processing'].includes(status.value))
const storageKey = computed(
  () => `maxkb-document-quality-task:${props.knowledgeId}:${props.documentId}`,
)

function loadModels() {
  loadSharedApi({ type: 'model', systemType: 'workspace' })
    .getSelectModelList({ model_type: 'LLM' })
    .then((res: any) => {
      modelOptions.value = groupBy(res?.data || [], 'provider')
    })
}

function open() {
  pollingGeneration += 1
  visible.value = true
  result.value = { before: [], after: [], report: {} }
  taskId.value = window.sessionStorage.getItem(storageKey.value) || ''
  if (taskId.value) {
    status.value = 'queued'
    poll()
  } else {
    status.value = ''
    loadModels()
  }
}

function poll() {
  if (!taskId.value) return
  const generation = pollingGeneration
  const currentTaskId = taskId.value
  api().getDocumentQualityTask(props.knowledgeId, props.documentId, taskId.value)
    .then((res: any) => {
      if (generation !== pollingGeneration || currentTaskId !== taskId.value || !visible.value) return
      pollingFailures = 0
      const task = res.data || {}
      status.value = task.status
      progress.value = task.progress || 0
      message.value = task.message || ''
      if (task.status === 'completed') {
        result.value = task.result
        return
      }
      if (task.status === 'failed' || task.status === 'cancelled') return
      timer = setTimeout(poll, 1000)
    })
    .catch(() => {
      if (generation !== pollingGeneration || currentTaskId !== taskId.value || !visible.value) return
      pollingFailures += 1
      if (pollingFailures < 3) {
        timer = setTimeout(poll, 2000)
      } else {
        status.value = 'failed'
        message.value = t('views.document.quality.pollFailed')
      }
    })
}

async function startTask() {
  if (starting.value) return
  starting.value = true
  try {
    const res: any = await api().createDocumentQualityTask(
      props.knowledgeId,
      props.documentId,
      modelId.value,
    )
    pollingGeneration += 1
    taskId.value = res.data.task_id
    window.sessionStorage.setItem(storageKey.value, taskId.value)
    status.value = 'queued'
    poll()
  } catch {
    ElMessage.error(t('views.document.quality.failed'))
  } finally {
    starting.value = false
  }
}

async function cancelTask() {
  if (cancelling.value) return
  cancelling.value = true
  try {
    await api().cancelDocumentQualityTask(props.knowledgeId, props.documentId, taskId.value)
    pollingGeneration += 1
    if (timer) clearTimeout(timer)
    status.value = 'cancelled'
    window.sessionStorage.removeItem(storageKey.value)
    visible.value = false
    ElMessage.success(t('views.document.quality.cancelled'))
  } catch {
    ElMessage.error(t('views.document.quality.failed'))
  } finally {
    cancelling.value = false
  }
}

async function applyTask() {
  if (applying.value) return
  try {
    await ElMessageBox.confirm(
      t('views.document.quality.applyConfirm'),
      t('views.document.quality.apply'),
      { type: 'warning' },
    )
    applying.value = true
    await api().applyDocumentQualityTask(props.knowledgeId, props.documentId, taskId.value)
    pollingGeneration += 1
    window.sessionStorage.removeItem(storageKey.value)
    visible.value = false
    ElMessage.success(t('views.document.quality.applied'))
    emit('refresh')
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(t('views.document.quality.failed'))
    }
  } finally {
    applying.value = false
  }
}

function resetTask() {
  pollingGeneration += 1
  if (timer) clearTimeout(timer)
  window.sessionStorage.removeItem(storageKey.value)
  taskId.value = ''
  status.value = ''
  progress.value = 0
  message.value = ''
  loadModels()
}

watch(visible, (value) => {
  if (!value) {
    pollingGeneration += 1
    if (timer) clearTimeout(timer)
  }
})

onBeforeUnmount(() => {
  pollingGeneration += 1
  if (timer) clearTimeout(timer)
})
defineExpose({ open })
</script>

<style scoped>
.pre-wrap { white-space: pre-wrap; word-break: break-word; }
</style>
