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
                    <div class="title mb-8">{{ $t('views.document.setRules.model.label') }}</div>
                    <ModelSelect
                      v-model="activeModelId"
                      :placeholder="$t('views.document.setRules.model.visionPlaceholder')"
                      :options="visionModelOptions"
                      @submitModel="getSelectModel('IMAGE')"
                      showFooter
                      :model-type="'IMAGE'"
                    />
                  </div>
                </el-card>
              </el-radio-group>
            </div>
          </el-scrollbar>
          <div>
            <el-checkbox
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
        </div>

        <div v-loading="loading">
          <ParagraphPreview v-model:data="paragraphList" :isConnect="checkedConnect" :knowledge-id="id"/>
        </div>
      </el-col>
    </el-row>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch } from 'vue'
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
const llmModelOptions = ref<any>({})
const visionModelOptions = ref<any>({})
const checkedConnect = ref<boolean>(false)
const draftKey = computed(() => String(id || ''))
const currentDraft = computed(() => {
  return knowledge.documentUploadDraft?.key === draftKey.value ? knowledge.documentUploadDraft : null
})
const draftProgress = computed(() => currentDraft.value?.progress || 0)
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
  if (status === 'parsing') {
    return t('views.document.setRules.progress.parsing')
  }
  if (status === 'ready') {
    return t('views.document.setRules.progress.ready')
  }
  if (status === 'failed') {
    return t('views.document.setRules.progress.failed')
  }
  return ''
})
const progressTip = computed(() => {
  const fileNames = currentDraft.value?.fileNames || []
  return fileNames.length > 0
    ? `${t('views.document.setRules.progress.files')}${fileNames.join('、')}`
    : t('views.document.setRules.progress.draft')
})

const firstChecked = ref(true)

const form = reactive<{
  patterns: Array<string>
  limit: number
  with_filter: boolean
  llm_model_id: string
  vision_model_id: string
  [propName: string]: any
}>({
  patterns: [],
  limit: 500,
  with_filter: true,
  llm_model_id: '',
  vision_model_id: '',
})

const isModelSplit = computed(() => radio.value === '3' || radio.value === '4')
const splitStrategy = computed(() => {
  if (radio.value === '3') {
    return 'llm_text'
  }
  if (radio.value === '4') {
    return 'llm_vision'
  }
  return ''
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
  return loading.value || (isModelSplit.value && !activeModelId.value)
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
      llm_model_id: form.llm_model_id,
      vision_model_id: form.vision_model_id,
    },
  })
}

function applyDraft(draft: DocumentUploadDraft | null) {
  if (!draft || draft.key !== draftKey.value) {
    return
  }
  if ((draft.status === 'uploading' || draft.status === 'parsing') && !draft.startedByUser) {
    knowledge.clearDocumentUploadDraft()
    loading.value = false
    paragraphList.value = []
    return
  }
  radio.value = draft.radio || '1'
  form.patterns = [...(draft.form?.patterns || [])]
  form.limit = draft.form?.limit || 500
  form.with_filter = draft.form?.with_filter ?? true
  form.llm_model_id = draft.form?.llm_model_id || ''
  form.vision_model_id = draft.form?.vision_model_id || ''
  checkedConnect.value = Boolean(draft.checkedConnect)
  paragraphList.value = draft.paragraphList || []
  loading.value = draft.status === 'uploading' || draft.status === 'parsing'
}

function postParagraphList(list: any[]) {
  list.map((item: any) => {
    if (item.name.length > 128) {
      item.name = cutFilename(item.name, 128)
    }
    if (checkedConnect.value) {
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
    fd.append('model_id', activeModelId.value)
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
    form: {
      patterns: [...form.patterns],
      limit: form.limit,
      with_filter: form.with_filter,
      llm_model_id: form.llm_model_id,
      vision_model_id: form.vision_model_id,
    },
    updatedAt: Date.now(),
  })

  const onUploadProgress: UploadProgressHandler = (progressEvent) => {
    const total = progressEvent.total || totalSize
    if (!total) {
      return
    }
    const uploadPercent = Math.round((progressEvent.loaded / total) * 90)
    patchCurrentDraft({
      status: progressEvent.loaded >= total ? 'parsing' : 'uploading',
      progress: Math.min(progressEvent.loaded >= total ? 95 : uploadPercent, 95),
    })
  }

  const request = loadSharedApi({ type: 'document', systemType: apiType.value })
    .postSplitDocument(id, fd, onUploadProgress)
    .then((res: any) => {
      const list = postParagraphList(res.data)

      paragraphList.value = list
      loading.value = false
      patchCurrentDraft({
        status: 'ready',
        progress: 100,
        paragraphList: list,
      })
    })
    .catch(() => {
      loading.value = false
      patchCurrentDraft({
        status: 'failed',
        progress: draftProgress.value,
        message: t('views.document.setRules.progress.failed'),
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
  if (radio.value === '3') {
    getSelectModel('LLM')
  }
  if (radio.value === '4') {
    getSelectModel('IMAGE')
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
  () => knowledge.documentUploadDraft,
  (draft) => {
    applyDraft(draft)
  },
  { deep: true },
)

onMounted(() => {
  if (currentDraft.value) {
    applyDraft(currentDraft.value)
    initModelOptions()
  }
})

defineExpose({
  paragraphList,
  checkedConnect,
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
