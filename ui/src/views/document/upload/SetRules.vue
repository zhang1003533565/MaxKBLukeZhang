<template>
  <div class="set-rules">
    <el-row>
      <el-col :span="10" class="p-24">
        <h4 class="title-decoration-1 mb-16">{{ $t('views.document.setRules.title.setting') }}</h4>
        <div class="set-rules__right">
          <el-scrollbar>
            <div class="left-height" @click.stop>
              <el-radio-group v-model="radio" class="card__radio">
                <el-card shadow="never" class="mb-16" :class="radio === '1' ? 'border-active' : ''">
                  <el-radio value="1" size="large">
                    <p class="mb-4">{{ $t('views.document.setRules.intelligent.label') }}</p>
                    <el-text type="info">{{
                      $t('views.document.setRules.intelligent.text')
                    }}</el-text>
                  </el-radio>
                </el-card>
                <el-card shadow="never" class="mb-16" :class="radio === '2' ? 'border-active' : ''">
                  <el-radio value="2" size="large">
                    <p class="mb-4">{{ $t('views.document.setRules.advanced.label') }}</p>
                    <el-text type="info">
                      {{ $t('views.document.setRules.advanced.text') }}
                    </el-text>
                  </el-radio>

                  <el-card
                    v-if="radio === '2'"
                    shadow="never"
                    class="card-never mt-16"
                    style="margin-left: 30px"
                  >
                    <div class="set-rules__form">
                      <div class="form-item mb-16">
                        <div class="title flex align-center mb-8">
                          <span style="margin-right: 4px">{{
                            $t('views.document.setRules.patterns.label')
                          }}</span>
                          <el-tooltip
                            effect="dark"
                            :content="$t('views.document.setRules.patterns.tooltip')"
                            placement="right"
                          >
                            <AppIcon iconName="app-warning" class="app-warning-icon"></AppIcon>
                          </el-tooltip>
                        </div>
                        <div @click.stop>
                          <el-select
                            v-model="form.patterns"
                            multiple
                            :reserve-keyword="false"
                            allow-create
                            default-first-option
                            filterable
                            :placeholder="$t('views.document.setRules.patterns.placeholder')"
                          >
                            <el-option
                              v-for="(item, index) in splitPatternList"
                              :key="index"
                              :label="item.key"
                              :value="item.value"
                            >
                            </el-option>
                          </el-select>
                        </div>
                      </div>
                      <div class="form-item mb-16">
                        <div class="title mb-8">
                          {{ $t('views.document.setRules.limit.label') }}
                        </div>
                        <el-slider
                          v-model="form.limit"
                          show-input
                          :show-input-controls="false"
                          :min="50"
                          :max="100000"
                        />
                      </div>
                      <div class="form-item mb-16">
                        <div class="title mb-8">
                          {{ $t('views.document.setRules.with_filter.label') }}
                        </div>
                        <el-switch size="small" v-model="form.with_filter" />
                        <div style="margin-top: 4px">
                          <el-text type="info">
                            {{ $t('views.document.setRules.with_filter.text') }}</el-text
                          >
                        </div>
                      </div>
                    </div>
                  </el-card>
                </el-card>
                <el-card shadow="never" class="mb-16" :class="radio === '5' ? 'border-active' : ''">
                  <el-radio value="5" size="large">
                    <p class="mb-4">{{ $t('views.document.setRules.qa.label') }}</p>
                    <el-text type="info">
                      {{ $t('views.document.setRules.qa.text') }}
                    </el-text>
                  </el-radio>
                  <div v-if="radio === '5'" class="model-select mt-16" style="margin-left: 30px">
                    <div class="title mb-8">
                      {{ $t('views.document.setRules.qaParseMode.label') }}
                    </div>
                    <el-select v-model="form.qa_parse_mode" class="w-full">
                      <el-option
                        v-for="item in qaParseModeOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                    <template v-if="qaNeedsTextModel">
                      <div class="title mt-16 mb-8">
                        {{ $t('views.document.setRules.model.qaLabel') }}
                      </div>
                      <ModelSelect
                        v-model="activeModelId"
                        :placeholder="$t('views.document.setRules.model.qaPlaceholder')"
                        :options="llmModelOptions"
                        @submitModel="getSelectModel('LLM')"
                        showFooter
                        :model-type="'LLM'"
                      />
                    </template>
                    <el-switch
                      v-model="form.quality_optimize"
                      class="mt-16"
                      :active-text="$t('views.document.setRules.quality.label')"
                    />
                  </div>
                </el-card>
                <el-card shadow="never" class="mb-16" :class="radio === '3' ? 'border-active' : ''">
                  <el-radio value="3" size="large">
                    <p class="mb-4">{{ $t('views.document.setRules.llmText.label') }}</p>
                    <el-text type="info">
                      {{ $t('views.document.setRules.llmText.text') }}
                    </el-text>
                  </el-radio>

                  <div v-if="radio === '3'" class="model-select mt-16" style="margin-left: 30px">
                    <div class="title mb-8">{{ $t('views.document.setRules.model.label') }}</div>
                    <ModelSelect
                      v-model="activeModelId"
                      :placeholder="$t('views.document.setRules.model.llmPlaceholder')"
                      :options="llmModelOptions"
                      @submitModel="getSelectModel('LLM')"
                      showFooter
                      :model-type="'LLM'"
                    />
                    <el-switch
                      v-model="form.quality_optimize"
                      class="mt-16"
                      :active-text="$t('views.document.setRules.quality.label')"
                    />
                  </div>
                </el-card>
                <el-card shadow="never" class="mb-16" :class="radio === '4' ? 'border-active' : ''">
                  <el-radio value="4" size="large">
                    <p class="mb-4">{{ $t('views.document.setRules.llmVision.label') }}</p>
                    <el-text type="info">
                      {{ $t('views.document.setRules.llmVision.text') }}
                    </el-text>
                  </el-radio>

                  <div v-if="radio === '4'" class="model-select mt-16" style="margin-left: 30px">
                    <div class="title mb-8">
                      {{ $t('views.document.setRules.model.visionLabel') }}
                    </div>
                    <ModelSelect
                      v-model="form.vision_model_id"
                      :placeholder="$t('views.document.setRules.model.visionPlaceholder')"
                      :options="visionModelOptions"
                      @submitModel="getSelectModel('IMAGE')"
                      showFooter
                      :model-type="'IMAGE'"
                    />
                    <div class="title mt-16 mb-8">
                      {{ $t('views.document.setRules.model.llmLabel') }}
                    </div>
                    <ModelSelect
                      v-model="form.llm_model_id"
                      :placeholder="$t('views.document.setRules.model.llmPlaceholder')"
                      :options="llmModelOptions"
                      @submitModel="getSelectModel('LLM')"
                      showFooter
                      :model-type="'LLM'"
                    />
                    <el-switch
                      v-model="form.quality_optimize"
                      class="mt-16"
                      :active-text="$t('views.document.setRules.quality.label')"
                    />
                  </div>
                </el-card>
              </el-radio-group>
            </div>
          </el-scrollbar>
          <div>
            <el-checkbox
              v-if="!isQASplitMode"
              v-model="checkedConnect"
              @change="changeHandle"
              style="white-space: normal"
            >
              {{ $t('views.document.setRules.checkedConnect.label') }}
            </el-checkbox>
          </div>
          <div class="text-right mt-8">
            <el-button @click="splitDocument" :disabled="previewDisabled">
              {{ $t('views.document.buttons.preview') }}</el-button
            >
          </div>
        </div>
      </el-col>

      <el-col :span="14" class="p-24 border-l">
        <h4 class="title-decoration-1 mb-8">{{ $t('views.document.setRules.title.preview') }}</h4>
        <div v-if="currentDraft" class="upload-progress mb-16">
          <div class="flex-between mb-8">
            <span class="bolder">{{ progressTitle }}</span>
            <el-text type="info" size="small">{{ draftProgress }}%</el-text>
          </div>
          <el-progress :percentage="draftProgress" :status="progressStatus" />
          <el-text type="info" size="small" class="upload-progress__tip">
            {{ progressTip }}
          </el-text>
          <div v-if="canCancelTask" class="text-right mt-8">
            <el-button type="danger" plain :loading="cancelLoading" @click="cancelSplitTask">
              {{ $t('views.document.setRules.progress.cancelButton') }}
            </el-button>
          </div>
        </div>

        <div v-loading="loading">
          <el-alert
            v-if="qualityReport"
            class="mb-16"
            type="success"
            :closable="false"
            :title="$t('views.document.setRules.quality.reportTitle')"
            :description="qualityReportText"
          />
          <ParagraphPreview
            v-model:data="paragraphList"
            :isConnect="preserveProblemList"
            :knowledge-id="id"
            :item-label="previewItemLabel"
          />
        </div>
      </el-col>
    </el-row>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ParagraphPreview from '@/views/knowledge/component/ParagraphPreview.vue'
import { useRoute } from 'vue-router'
import { cutFilename } from '@/utils/common'
import useStore from '@/stores'
import type { KeyValue } from '@/api/type/common'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { t } from '@/locales'
import type { UploadProgressHandler } from '@/request/index'
import type { DocumentUploadDraft } from '@/stores/modules/knowledge'
import { groupBy } from 'lodash'
const { knowledge } = useStore()
const documentsFiles = computed(() => knowledge.documentsFiles)
const splitPatternList = ref<Array<KeyValue<string, string>>>([])
const route = useRoute()
const {
  query: { id}, // id为knowledgeID
} = route as any

const apiType = computed(() => {
  if (route.path.includes('shared')) {
    return 'systemShare'
  } else if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})

const radio = ref('1')
const loading = ref(false)
const paragraphList = ref<any[]>([])
const patternLoading = ref<boolean>(false)
const cancelLoading = ref(false)
const llmModelOptions = ref<any>({})
const visionModelOptions = ref<any>({})
const checkedConnect = ref<boolean>(false)
const draftKey = computed(() => String(id || ''))
const currentDraft = computed(() => {
  return knowledge.documentUploadDraft?.key === draftKey.value ? knowledge.documentUploadDraft : null
})
const draftProgress = computed(() => currentDraft.value?.progress || 0)
const taskProcessed = computed(() => currentDraft.value?.processed || 0)
const taskTotal = computed(() => currentDraft.value?.total || 0)
const taskRemaining = computed(() => currentDraft.value?.remaining || 0)
const progressStatus = computed(() => {
  if (currentDraft.value?.status === 'ready') {
    return 'success'
  }
  if (currentDraft.value?.status === 'failed') {
    return 'exception'
  }
  return undefined
})
const progressTitle = computed(() => {
  const status = currentDraft.value?.status
  if (status === 'uploading') {
    return t('views.document.setRules.progress.uploading')
  }
  if (status === 'queued') {
    return t('views.document.setRules.progress.queued')
  }
  if (status === 'processing') {
    return currentDraft.value?.message || t('views.document.setRules.progress.processing')
  }
  if (status === 'parsing') {
    return t('views.document.setRules.progress.parsing')
  }
  if (status === 'ready') {
    return t('views.document.setRules.progress.ready')
  }
  if (status === 'failed') {
    return t('views.document.setRules.progress.failed')
  }
  if (status === 'cancelled') {
    return t('views.document.setRules.progress.cancelled')
  }
  return ''
})
const canCancelTask = computed(() => {
  return Boolean(
    currentDraft.value?.backendTaskId &&
      ['queued', 'processing', 'parsing'].includes(currentDraft.value.status),
  )
})
const progressTip = computed(() => {
  if (taskTotal.value > 0) {
    return t('views.document.setRules.progress.counts', {
      processed: taskProcessed.value,
      total: taskTotal.value,
      remaining: taskRemaining.value,
    })
  }
  const fileNames = currentDraft.value?.fileNames || []
  return fileNames.length > 0
    ? `${t('views.document.setRules.progress.files')}${fileNames.join('、')}`
    : t('views.document.setRules.progress.draft')
})

const firstChecked = ref(true)
let pollingTimer: ReturnType<typeof setTimeout> | undefined
let pollingFailureCount = 0
let componentActive = true
let pollingGeneration = 0

const form = reactive<{
  patterns: Array<string>
  limit: number
  with_filter: boolean
  qa_parse_mode: string
  llm_model_id: string
  vision_model_id: string
  quality_optimize: boolean
  [propName: string]: any
}>({
  patterns: [],
  limit: 500,
  with_filter: true,
  qa_parse_mode: 'auto',
  llm_model_id: '',
  vision_model_id: '',
  quality_optimize: false,
})
const qaParseModeOptions = computed(() => [
  {
    label: t('views.document.setRules.qaParseMode.auto'),
    value: 'auto',
  },
  {
    label: t('views.document.setRules.qaParseMode.rule'),
    value: 'rule',
  },
  {
    label: t('views.document.setRules.qaParseMode.llm'),
    value: 'llm',
  },
])
const qualityReport = computed(() => {
  const reports = paragraphList.value.map((item) => item.quality_report).filter(Boolean)
  if (!reports.length) {
    return null
  }
  return reports.reduce(
    (total, report) => {
      Object.keys(total).forEach((key) => {
        total[key] += Number(report[key] || 0)
      })
      return total
    },
    {
      removed_noise: 0,
      titles_rewritten: 0,
      split_paragraphs: 0,
      merged_paragraphs: 0,
      fallback_batches: 0,
      fallback_images: 0,
      removed_page_numbers: 0,
      preserved_numeric_lines: 0,
      joined_pdf_lines: 0,
      removed_duplicates: 0,
    } as Record<string, number>,
  )
})
const qualityReportText = computed(() => {
  const report = qualityReport.value
  if (!report) {
    return ''
  }
  return t('views.document.setRules.quality.report', report)
})

const splitStrategy = computed(() => {
  if (radio.value === '5') {
    return 'qa'
  }
  if (radio.value === '3') {
    return 'llm_text'
  }
  if (radio.value === '4') {
    return 'llm_vision'
  }
  return ''
})
const isQASplitMode = computed(() => radio.value === '5')
const preserveProblemList = computed(() => checkedConnect.value || isQASplitMode.value)
const previewItemLabel = computed(() => isQASplitMode.value ? t('views.document.setRules.qa.previewUnit') : '')
const qaNeedsTextModel = computed(() => {
  return isQASplitMode.value && (form.qa_parse_mode !== 'rule' || form.quality_optimize)
})
const activeModelId = computed({
  get: () => (radio.value === '4' ? form.vision_model_id : form.llm_model_id),
  set: (value: string) => {
    if (radio.value === '4') {
      form.vision_model_id = value
    } else {
      form.llm_model_id = value
    }
    patchDraftConfig()
  },
})
const previewDisabled = computed(() => {
  if (loading.value) {
    return true
  }
  if (radio.value === '3') {
    return !form.llm_model_id
  }
  if (radio.value === '5') {
    return qaNeedsTextModel.value && !form.llm_model_id
  }
  if (radio.value === '4') {
    return !form.vision_model_id || !form.llm_model_id
  }
  return false
})
const canImport = computed(() => {
  return !loading.value && paragraphList.value.length > 0 && currentDraft.value?.status === 'ready'
})

function changeHandle(val: boolean) {
  if (val && firstChecked.value) {
    paragraphList.value = paragraphList.value.map((item: any) => ({
      ...item,
      content: item.content.map((v: any) => ({
        ...v,
        problem_list: v.title.trim()
          ? [
              {
                content: v.title.trim(),
              },
            ]
          : [],
      })),
    }))
    firstChecked.value = false
  }
  knowledge.patchDocumentUploadDraft({
    checkedConnect: val,
    paragraphList: paragraphList.value,
  })
}

function patchDraftConfig() {
  knowledge.patchDocumentUploadDraft({
    checkedConnect: checkedConnect.value,
    radio: radio.value,
    form: {
      patterns: [...form.patterns],
      limit: form.limit,
      with_filter: form.with_filter,
      qa_parse_mode: form.qa_parse_mode,
      llm_model_id: form.llm_model_id,
      vision_model_id: form.vision_model_id,
      quality_optimize: form.quality_optimize,
    },
  })
}

function applyDraft(draft: DocumentUploadDraft | null) {
  if (!draft || draft.key !== draftKey.value) {
    return
  }
  if (
    (draft.status === 'uploading' || draft.status === 'parsing') &&
    !draft.startedByUser &&
    !draft.backendTaskId
  ) {
    knowledge.clearDocumentUploadDraft()
    loading.value = false
    paragraphList.value = []
    return
  }
  radio.value = draft.radio || '1'
  form.patterns = [...(draft.form?.patterns || [])]
  form.limit = draft.form?.limit || 500
  form.with_filter = draft.form?.with_filter ?? true
  form.qa_parse_mode = draft.form?.qa_parse_mode || 'auto'
  form.llm_model_id = draft.form?.llm_model_id || ''
  form.vision_model_id = draft.form?.vision_model_id || ''
  form.quality_optimize = draft.form?.quality_optimize ?? false
  checkedConnect.value = Boolean(draft.checkedConnect)
  paragraphList.value = draft.paragraphList || []
  loading.value = ['uploading', 'queued', 'processing', 'parsing'].includes(draft.status)
}

function stopPolling() {
  pollingGeneration += 1
  if (pollingTimer) {
    clearTimeout(pollingTimer)
    pollingTimer = undefined
  }
}

function pollSplitTask(backendTaskId: string, taskId: string) {
  if (!componentActive) {
    return
  }
  stopPolling()
  const generation = pollingGeneration
  loadSharedApi({ type: 'document', systemType: apiType.value })
    .getSplitDocumentTask(id, backendTaskId)
    .then((res: any) => {
      if (
        !componentActive ||
        generation !== pollingGeneration ||
        knowledge.documentUploadDraft?.taskId !== taskId
      ) {
        return
      }
      pollingFailureCount = 0
      const task = res.data || {}
      if (task.status === 'completed') {
        const list = postParagraphList(task.result || [])
        paragraphList.value = list
        loading.value = false
        knowledge.patchDocumentUploadDraft({
          status: 'ready',
          progress: 100,
          stage: 'completed',
          processed: task.processed || 1,
          total: task.total || 1,
          remaining: 0,
          message: task.message,
          paragraphList: list,
        })
        return
      }
      if (task.status === 'failed') {
        loading.value = false
        paragraphList.value = []
        knowledge.patchDocumentUploadDraft({
          status: 'failed',
          stage: 'failed',
          message: task.error || task.message || t('views.document.setRules.progress.failed'),
          paragraphList: [],
        })
        return
      }
      if (task.status === 'cancelled') {
        loading.value = false
        paragraphList.value = []
        knowledge.patchDocumentUploadDraft({
          status: 'cancelled',
          stage: 'cancelled',
          message: task.message || t('views.document.setRules.progress.cancelled'),
          paragraphList: [],
        })
        return
      }
      knowledge.patchDocumentUploadDraft({
        status: task.status === 'queued' ? 'queued' : 'processing',
        progress: Math.max(knowledge.documentUploadDraft?.progress || 0, task.progress || 0),
        stage: task.stage,
        processed: task.processed || 0,
        total: task.total || 0,
        remaining: task.remaining || 0,
        message: task.message,
      })
      pollingTimer = setTimeout(() => pollSplitTask(backendTaskId, taskId), 1000)
    })
    .catch(() => {
      if (
        !componentActive ||
        generation !== pollingGeneration ||
        knowledge.documentUploadDraft?.taskId !== taskId
      ) {
        return
      }
      pollingFailureCount += 1
      if (pollingFailureCount < 3) {
        pollingTimer = setTimeout(() => pollSplitTask(backendTaskId, taskId), 2000)
        return
      }
      loading.value = false
      paragraphList.value = []
      knowledge.patchDocumentUploadDraft({
        status: 'failed',
        message: t('views.document.setRules.progress.expired'),
        paragraphList: [],
      })
    })
}

async function cancelSplitTask() {
  const backendTaskId = currentDraft.value?.backendTaskId
  if (!backendTaskId || cancelLoading.value) {
    return
  }
  try {
    await ElMessageBox.confirm(
      t('views.document.setRules.progress.cancelConfirmMessage'),
      t('views.document.setRules.progress.cancelConfirmTitle'),
      {
        type: 'warning',
        confirmButtonText: t('views.document.setRules.progress.cancelButton'),
        cancelButtonText: t('views.document.setRules.progress.cancelKeepButton'),
      },
    )
  } catch {
    return
  }

  stopPolling()
  cancelLoading.value = true
  try {
    await loadSharedApi({ type: 'document', systemType: apiType.value })
      .cancelSplitDocumentTask(id, backendTaskId)
    stopPolling()
    loading.value = false
    paragraphList.value = []
    knowledge.patchDocumentUploadDraft({
      status: 'cancelled',
      stage: 'cancelled',
      message: t('views.document.setRules.progress.cancelled'),
      paragraphList: [],
    })
    ElMessage.success(t('views.document.setRules.progress.cancelSuccess'))
  } catch {
    ElMessage.error(t('views.document.setRules.progress.cancelFailed'))
    const taskId = currentDraft.value?.taskId
    if (taskId && currentDraft.value?.backendTaskId) {
      pollSplitTask(currentDraft.value.backendTaskId, taskId)
    }
  } finally {
    cancelLoading.value = false
  }
}

function postParagraphList(list: any[]) {
  list.map((item: any) => {
    if (item.name.length > 128) {
      item.name = cutFilename(item.name, 128)
    }
    if (checkedConnect.value && !isQASplitMode.value) {
      item.content.map((v: any) => {
        v['problem_list'] = v.title.trim()
          ? [
              {
                content: v.title.trim(),
              },
            ]
          : []
      })
    }
  })
  return list
}

function splitDocument() {
  if (loading.value) {
    return
  }
  loading.value = true
  stopPolling()
  pollingFailureCount = 0
  paragraphList.value = []
  const fd = new FormData()
  const uploadFiles = documentsFiles.value.filter((item) => item?.raw)
  const totalSize = uploadFiles.reduce((sum, item) => sum + (item.size || item.raw?.size || 0), 0)
  uploadFiles.forEach((item) => {
    if (item?.raw) {
      fd.append('file', item?.raw)
    }
  })
  if (radio.value === '2') {
    Object.keys(form).forEach((key) => {
      if (key == 'patterns') {
        form.patterns.forEach((item) => fd.append('patterns', item))
      } else if (['limit', 'with_filter'].includes(key)) {
        fd.append(key, form[key])
      }
    })
  }
  if (splitStrategy.value) {
    fd.append('split_strategy', splitStrategy.value)
    if (splitStrategy.value === 'qa') {
      fd.append('qa_parse_mode', form.qa_parse_mode)
      if (qaNeedsTextModel.value) {
        fd.append('model_id', form.llm_model_id)
      }
    } else if (splitStrategy.value === 'llm_text') {
      fd.append('model_id', form.llm_model_id)
    } else if (splitStrategy.value === 'llm_vision') {
      fd.append('vision_model_id', form.vision_model_id)
      fd.append('llm_model_id', form.llm_model_id)
    }
    if (['qa', 'llm_text', 'llm_vision'].includes(splitStrategy.value)) {
      fd.append('quality_optimize', String(form.quality_optimize))
    }
  }

  const taskId = `${Date.now()}-${Math.random()}`
  const patchCurrentDraft = (draft: Partial<DocumentUploadDraft>) => {
    if (knowledge.documentUploadDraft?.taskId === taskId) {
      knowledge.patchDocumentUploadDraft(draft)
    }
  }

  knowledge.setDocumentUploadDraft({
    key: draftKey.value,
    taskId,
    status: 'uploading',
    progress: 0,
    fileNames: uploadFiles.map((item) => item.name || item.raw?.name || ''),
    fileCount: uploadFiles.length,
    totalSize,
    paragraphList: [],
    checkedConnect: checkedConnect.value,
    radio: radio.value,
    startedByUser: true,
    backendTaskId: undefined,
    stage: 'uploading',
    processed: 0,
    total: 0,
    remaining: 0,
    form: {
      patterns: [...form.patterns],
      limit: form.limit,
      with_filter: form.with_filter,
      qa_parse_mode: form.qa_parse_mode,
      llm_model_id: form.llm_model_id,
      vision_model_id: form.vision_model_id,
      quality_optimize: form.quality_optimize,
    },
    updatedAt: Date.now(),
  })

  const onUploadProgress: UploadProgressHandler = (progressEvent) => {
    const total = progressEvent.total || totalSize
    if (!total) {
      return
    }
    const uploadPercent = Math.round((progressEvent.loaded / total) * 100)
    patchCurrentDraft({
      status: 'uploading',
      progress: Math.min(uploadPercent, 100),
    })
  }

  const documentApi = loadSharedApi({ type: 'document', systemType: apiType.value })
  const request = apiType.value === 'workspace'
    ? documentApi
    .postSplitDocumentTask(id, fd, onUploadProgress)
    .then((res: any) => {
      const backendTaskId = res.data?.task_id
      if (!backendTaskId) {
        throw new Error('Missing split preview task id')
      }
      patchCurrentDraft({
        status: 'queued',
        progress: 0,
        backendTaskId,
        stage: 'queued',
        message: t('views.document.setRules.progress.queued'),
      })
      pollSplitTask(backendTaskId, taskId)
    })
    .catch(() => {
      loading.value = false
      paragraphList.value = []
      patchCurrentDraft({
        status: 'failed',
        progress: draftProgress.value,
        message: t('views.document.setRules.progress.failed'),
        paragraphList: [],
      })
    })
    : documentApi.postSplitDocument(id, fd, onUploadProgress).then((res: any) => {
      const list = postParagraphList(res.data || [])
      paragraphList.value = list
      loading.value = false
      patchCurrentDraft({
        status: 'ready',
        progress: 100,
        stage: 'completed',
        processed: list.length,
        total: list.length,
        remaining: 0,
        paragraphList: list,
      })
    }).catch(() => {
      loading.value = false
      paragraphList.value = []
      patchCurrentDraft({
        status: 'failed',
        message: t('views.document.setRules.progress.failed'),
        paragraphList: [],
      })
    })

  patchCurrentDraft({ promise: request })
}

const initSplitPatternList = () => {
  loadSharedApi({ type: 'document', systemType: apiType.value })
    .listSplitPattern(id, patternLoading)
    .then((ok: any) => {
      splitPatternList.value = ok.data
    })
}

function getSelectModel(modelType: 'LLM' | 'IMAGE') {
  loadSharedApi({ type: 'model', systemType: apiType.value })
    .getSelectModelList({ model_type: modelType })
    .then((res: any) => {
      const options = groupBy(res?.data || [], 'provider')
      if (modelType === 'LLM') {
        llmModelOptions.value = options
      } else {
        visionModelOptions.value = options
      }
    })
}

function initModelOptions() {
  if (['3', '5'].includes(radio.value)) {
    getSelectModel('LLM')
  }
  if (radio.value === '4') {
    getSelectModel('IMAGE')
    getSelectModel('LLM')
  }
}

watch(radio, () => {
  patchDraftConfig()
  if (radio.value === '2') {
    initSplitPatternList()
  }
  initModelOptions()
})

watch(
  () => [form.llm_model_id, form.vision_model_id, form.qa_parse_mode, form.quality_optimize],
  () => patchDraftConfig(),
)

watch(
  () => knowledge.documentUploadDraft,
  (draft) => {
    applyDraft(draft)
  },
  { deep: true },
)

onMounted(() => {
  componentActive = true
  if (currentDraft.value) {
    applyDraft(currentDraft.value)
    initModelOptions()
    if (currentDraft.value.status === 'uploading' && !currentDraft.value.backendTaskId) {
      loading.value = false
      knowledge.patchDocumentUploadDraft({
        status: 'failed',
        message: t('views.document.setRules.progress.uploadInterrupted'),
      })
      return
    }
    if (
      currentDraft.value.backendTaskId &&
      ['queued', 'processing', 'parsing'].includes(currentDraft.value.status)
    ) {
      pollSplitTask(currentDraft.value.backendTaskId, currentDraft.value.taskId)
    }
  }
})

onBeforeUnmount(() => {
  componentActive = false
  stopPolling()
})

function shouldPreserveProblemList() {
  return preserveProblemList.value
}

defineExpose({
  paragraphList,
  checkedConnect,
  shouldPreserveProblemList,
  loading,
  canImport,
})
</script>
<style scoped lang="scss">
.set-rules {
  width: 100%;

  .left-height {
    max-height: calc(var(--create-knowledge-height) - 110px);
    overflow-x: hidden;
  }
  &__form {
    .title {
      font-size: 14px;
      font-weight: 400;
    }
  }
  .upload-progress {
    padding: 12px;
    border: 1px solid var(--el-border-color);
    border-radius: 6px;
    background: var(--el-fill-color-lighter);

    &__tip {
      display: block;
      margin-top: 8px;
      word-break: break-all;
    }
  }
}
</style>
