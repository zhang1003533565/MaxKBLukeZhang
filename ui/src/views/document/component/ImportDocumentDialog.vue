<template>
  <el-dialog
    :title="title"
    v-model="dialogVisible"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :destroy-on-close="true"
    width="550"
  >
    <el-form
      label-position="top"
      ref="formRef"
      :rules="rules"
      :model="form"
      require-asterisk-position="right"
    >
      <el-form-item>
        <template #label>
          <div class="flex align-center">
            <span class="mr-4">{{ $t('views.document.form.hit_handling_method.label') }}</span>
            <el-tooltip
              effect="dark"
              :content="$t('views.document.form.hit_handling_method.tooltip')"
              placement="right"
            >
              <AppIcon iconName="app-warning" class="app-warning-icon"></AppIcon>
            </el-tooltip>
          </div>
        </template>
        <el-radio-group v-model="form.hit_handling_method" class="radio-block mt-4">
          <template v-for="(value, key) of hitHandlingMethod" :key="key">
            <el-radio :value="key">{{ $t(value) }} </el-radio>
          </template>
        </el-radio-group>
      </el-form-item>
      <el-form-item
        prop="directly_return_similarity"
        v-if="form.hit_handling_method === 'directly_return'"
      >
        <div class="lighter w-full" style="margin-top: -20px">
          <span>{{ $t('views.document.form.similarity.label') }}</span>
          <el-input-number
            v-model="form.directly_return_similarity"
            :min="0"
            :max="1"
            :precision="3"
            :step="0.1"
            :value-on-clear="0"
            controls-position="right"
            size="small"
            class="ml-4 mr-4"
          /><span>{{ $t('views.document.form.similarity.placeholder') }}</span>
        </div>
      </el-form-item>
      <el-form-item prop="allow_download">
        <el-checkbox v-model="form.allow_download">
          {{ $t('views.document.form.allow_download') }}
        </el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click.prevent="dialogVisible = false"> {{ $t('common.cancel') }} </el-button>
        <el-button type="primary" @click="submit(formRef)" :loading="loading">
          {{ $t('common.confirm') }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import type { FormInstance } from 'element-plus'
import { MsgSuccess } from '@/utils/message'
import { hitHandlingMethod } from '@/enums/document'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { t } from '@/locales'
const route = useRoute()
const {
  params: { id },
} = route as any

const props = defineProps({
  title: String,
})

const apiType = computed(() => {
  if (route.path.includes('shared')) {
    return 'systemShare'
  } else if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})

const emit = defineEmits(['refresh'])
const formRef = ref()
const loading = ref<boolean>(false)
const form = ref<any>({
  hit_handling_method: 'optimization',
  directly_return_similarity: 0.9,
  allow_download: true,
})

// 文档设置
const documentId = ref('')

// 批量设置
const documentList = ref<Array<string>>([])

const rules = reactive({
  directly_return_similarity: [
    {
      required: true,
      message: t('views.document.form.similarity.requiredMessage'),
      trigger: 'blur',
    },
  ],
})

const dialogVisible = ref<boolean>(false)

watch(dialogVisible, (bool) => {
  if (!bool) {
    form.value = {
      source_url: '',
      selector: '',
      hit_handling_method: 'optimization',
      directly_return_similarity: 0.9,
      allow_download: true,
    }
    documentId.value = ''
    documentList.value = []
  }
})

const open = (row: any, list: Array<string>) => {
  if (row) {
    documentId.value = row.id
    form.value = {
      hit_handling_method: row.hit_handling_method,
      directly_return_similarity: row.directly_return_similarity,
      ...row.meta,
      meta: row.meta,
    }
  } else if (list) {
    // 批量设置
    documentList.value = list
  } else {
    return
  }
  dialogVisible.value = true
}

const submit = async (formEl: FormInstance | undefined) => {
  if (!formEl) return
  await formEl.validate((valid) => {
    if (valid) {
      if (documentId.value) {
        const obj = {
          hit_handling_method: form.value.hit_handling_method,
          directly_return_similarity: form.value.directly_return_similarity,
          meta: {
            ...form.value.meta,
            allow_download: form.value.allow_download,
          },
        }
        loadSharedApi({ type: 'document', systemType: apiType.value })
          .putDocument(id, documentId.value, obj, loading)
          .then(() => {
            MsgSuccess(t('common.settingSuccess'))
            emit('refresh')
            dialogVisible.value = false
          })
      } else if (documentList.value.length > 0) {
        // 批量设置
        const obj = {
          hit_handling_method: form.value.hit_handling_method,
          directly_return_similarity: form.value.directly_return_similarity,
          id_list: documentList.value,
          allow_download: form.value.allow_download,
        }
        loadSharedApi({ type: 'document', systemType: apiType.value })
          .putBatchEditHitHandling(id, obj, loading)
          .then(() => {
            MsgSuccess(t('common.settingSuccess'))
            emit('refresh')
            dialogVisible.value = false
          })
      }
    }
  })
}

defineExpose({ open })
</script>
<style lang="scss" scoped></style>
