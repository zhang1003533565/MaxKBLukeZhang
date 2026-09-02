<template>
  <div>
    <InfiniteScroll
      :size="paragraph_list.length"
      :total="modelValue.length"
      :page_size="page_size"
      v-model:current_page="current_page"
      @load="next()"
      :loading="loading"
    >
      <el-card
        v-for="(child, cIndex) in paragraph_list"
        :key="cIndex"
        shadow="never"
        class="paragraph-preview-card card-never mb-16"
        @mouseenter="cardEnter(cIndex)"
        @mouseleave="cardLeave()"
      >
        <div v-show="show === cIndex" class="mk-sticky">
          <el-card
            class="paragraph-box-operation mt-8 mr-8"
            shadow="always"
            style="--el-card-padding: 8px 12px; --el-card-border-radius: 8px"
            @click.stop
          >
            <!-- 编辑分段按钮 -->
            <el-button link @click="editHandle(child, cIndex)">
              <AppIcon iconName="app-edit"></AppIcon>
            </el-button>
            <!-- 删除分段按钮  -->
            <el-button link @click="deleteHandle(child, cIndex)">
              <AppIcon iconName="app-delete"></AppIcon>
            </el-button>
          </el-card>
        </div>
        <div class="flex-between">
          <span>{{ child.title || '-' }}</span>
        </div>
        <div class="lighter mt-12">
          <MdPreview
            ref="editorRef"
            editorId="preview-only"
            :modelValue="child.content"
            class="maxkb-md"
            style="background: none"
          />
        </div>
        <div
          v-if="isConnect && previewQuestionList(child).length"
          class="related-preview mt-8"
        >
          <span class="related-preview__label">
            {{ $t('views.paragraph.relatedProblem.previewTitle') }}
          </span>
          <el-tag
            v-for="(problem, problemIndex) in previewQuestionList(child)"
            :key="problemIndex"
            size="small"
            type="info"
            effect="plain"
            class="related-preview__tag"
          >
            <auto-tooltip :content="problem.content">
              <span class="related-preview__tag-text">{{ problem.content }}</span>
            </auto-tooltip>
          </el-tag>
        </div>
        <div
          v-if="isConnect && previewKeywordList(child).length"
          class="related-preview mt-8"
        >
          <span class="related-preview__label">
            {{ $t('views.paragraph.relatedProblem.keywordTitle') }}
          </span>
          <el-tag
            v-for="(keyword, keywordIndex) in previewKeywordList(child)"
            :key="keywordIndex"
            size="small"
            type="success"
            effect="plain"
            class="related-preview__tag"
          >
            <auto-tooltip :content="keyword.content">
              <span class="related-preview__tag-text">{{ keyword.content }}</span>
            </auto-tooltip>
          </el-tag>
        </div>
        <div class="lighter mt-12">
          <el-text type="info">
            {{ child.content.length }} {{ $t('views.paragraph.character_count') }}
          </el-text>
        </div>
      </el-card>
    </InfiniteScroll>

    <EditParagraphDialog
      ref="EditParagraphDialogRef"
      @updateContent="updateContent"
      :isConnect="isConnect"
      :knowledge-id="knowledgeId"
    />
  </div>
</template>
<script setup lang="ts">
import { cloneDeep } from 'lodash'
import { ref, computed, watchEffect } from 'vue'
import EditParagraphDialog from './EditParagraphDialog.vue'
import { MsgConfirm } from '@/utils/message'
import { t } from '@/locales'

const page_size = ref<number>(30)
const current_page = ref<number>(1)
const currentCIndex = ref<number>(0)
const EditParagraphDialogRef = ref()
const emit = defineEmits(['update:modelValue'])
const loading = ref<boolean>(false)
const localParagraphList = ref<any[]>([])
const questionTextRegExp = /[？?]\s*$/
const questionWordRegExp =
  /(什么|啥|哪些|哪种|如何|怎么|怎样|为什么|为何|是否|能否|可否|可以|能不能|要不要|需要|应该|应当|谁|哪里|哪儿|何时|多久|多少|怎么办|咋办|吗|呢)/
const previewQuestionPrefixRegExp =
  /^(请问一下|请教一下|想了解一下|能否告诉我|请告诉我|请帮我|请帮忙|想请问|请问|请教|想了解|想知道|麻烦您|麻烦|烦请|劳烦|请您|帮忙|请)\s*/
const previewQuestionSuffixRegExp = /(?:吗|呢|吧|呀|啊|么|嘛)+$/
const previewNormalizeRegExp = /[\s\u3000，,。！？?!；;:："'“”‘’（）()【】\[\]<>《》·、]/g
const markdownRegExp = /[#>*_`~\-[\]()+]/g
const keywordSplitRegExp =
  /[\s\u3000，,。！？?!；;:："'“”‘’（）()【】\[\]<>《》·、\n\r]+|以及|或者|并且|同时|根据|依据|依照|按照|应当|应该|需要|可以|不得|不能|进行|包括|适用于|制定|维护|保障|培养|提升|支持|引导|遵守|履行|取得|完成|参加|使用|申请/g
const keywordAtomSplitRegExp = /[的之与和及]/g
const keywordPatternRegExp =
  /[\u4e00-\u9fa5A-Za-z0-9]{2,18}(?:规定|制度|办法|流程|原则|范围|条件|要求|义务|权利|依据|资格|手续|学籍|考试|考核|复学|休学|退学|转学|转专业|注册|处分|奖励|奖学金|章程|法律|学生|研究生|本科|专科)/g
const fallbackKeywordStopwords = new Set([
  '什么',
  '哪些',
  '怎么',
  '如何',
  '是否',
  '可以',
  '需要',
  '应该',
  '应当',
  '不得',
  '不能',
  '进行',
  '以及',
  '或者',
  '问题',
  '答案',
  '情况',
  '内容',
  '一下',
  '请问',
])

const props = defineProps({
  modelValue: {
    type: Array<any>,
    default: () => [],
  },
  isConnect: Boolean,
  knowledgeId: String,
})

// 初始化加载数据
watchEffect(() => {
  if (props.modelValue && props.modelValue.length > 0) {
    const end = page_size.value * current_page.value
    localParagraphList.value = props.modelValue.slice(0, Math.min(end, props.modelValue.length))
  }
})

// 监听分页变化，只加载需要的数据
watchEffect(() => {
  const start = 0
  const end = page_size.value * current_page.value
  // 不管数据量多少，都确保获取所有应该显示的数据
  localParagraphList.value = props.modelValue.slice(start, Math.min(end, props.modelValue.length))
})

const paragraph_list = computed(() => {
  return localParagraphList.value
})

const show = ref<number | null>(null)
function cardEnter(cIndex: number) {
  show.value = cIndex
}

function cardLeave() {
  show.value = null
}

function normalizeProblemList(problemList: any[]): Array<{ content: string; kind?: string }> {
  if (!Array.isArray(problemList)) {
    return []
  }
  return problemList
    .map((item) => {
      if (typeof item === 'string') {
        const content = item.trim()
        return content ? { content } : null
      }
      if (!item || typeof item !== 'object') {
        return null
      }
      const content = String(item.content || '').trim()
      if (!content) {
        return null
      }
      return {
        content,
        kind: item.kind,
      }
    })
    .filter((item): item is { content: string; kind?: string } => Boolean(item))
}

function isQuestionText(content: string) {
  return questionTextRegExp.test(content) || questionWordRegExp.test(content)
}

function previewProblemKey(content: string) {
  return (content || '').trim()
}

function previewQuestionKey(content: string) {
  let value = previewProblemKey(content).toLowerCase()
  value = value.replace(previewNormalizeRegExp, '')
  value = value.replace(previewQuestionPrefixRegExp, '')
  value = value.replace(previewQuestionSuffixRegExp, '')
  return value
}

function previewProblemList(
  problemList: any[],
  matcher: (item: any) => boolean,
  limit: number,
  keyGetter = previewProblemKey,
): Array<{ content: string; kind?: string }> {
  const seen = new Set<string>()
  return normalizeProblemList(problemList)
    .filter(matcher)
    .filter((item) => {
      const key = keyGetter(item.content)
      if (!key || seen.has(key)) {
        return false
      }
      seen.add(key)
      return true
    })
    .slice(0, limit)
}

function getProblemList(child: any) {
  return Array.isArray(child) ? child : child?.problem_list
}

function previewQuestionList(child: any) {
  const explicitQuestions = previewProblemList(
    (Array.isArray(child?.related_questions) ? child.related_questions : []).map(
      (value: any) => ({
        content: typeof value === 'string' ? value : value?.content,
        kind: 'question',
      }),
    ),
    () => true,
    8,
    previewQuestionKey,
  )
  const fallbackQuestions = previewProblemList(
    getProblemList(child),
    (item) => item.kind === 'question' || (!item.kind && isQuestionText(item.content)),
    8,
    previewQuestionKey,
  )
  return previewProblemList([...explicitQuestions, ...fallbackQuestions], () => true, 8)
}

function normalizeKeywordCandidate(content: string) {
  const value = (content || '').replace(markdownRegExp, '').trim()
  if (!value || fallbackKeywordStopwords.has(value) || isQuestionText(value)) {
    return ''
  }
  if (!/[\u4e00-\u9fa5A-Za-z]/.test(value) || /^[\d\W_]+$/.test(value)) {
    return ''
  }
  if (value.length < 2 || value.length > 12) {
    return ''
  }
  return value
}

function fallbackKeywordList(child: any) {
  if (Array.isArray(child)) {
    return []
  }
  const text = `${child?.title || ''}\n${child?.content || ''}`.replace(markdownRegExp, ' ')
  const candidates = [
    ...(text.match(keywordPatternRegExp) || []),
    ...text.split(keywordSplitRegExp),
  ]
  const expandedCandidates = candidates.flatMap((candidate) => [
    candidate,
    ...String(candidate || '')
      .split(keywordAtomSplitRegExp)
      .map((item) => item.trim()),
  ])
  const seen = new Set<string>()
  const result: any[] = []
  for (const candidate of expandedCandidates) {
    const content = normalizeKeywordCandidate(candidate)
    const key = previewProblemKey(content)
    if (!content || !key || seen.has(key)) {
      continue
    }
    seen.add(key)
    result.push({ content, kind: 'keyword' })
    if (result.length >= 8) {
      break
    }
  }
  return result
}

function previewKeywordList(child: any) {
  const explicitKeywords = previewProblemList(
    (Array.isArray(child?.keywords) ? child.keywords : []).map((value: any) => ({
      content: typeof value === 'string' ? value : value?.content,
      kind: 'keyword',
    })),
    () => true,
    8,
  )
  const problemKeywords = previewProblemList(
    getProblemList(child),
    (item) => item.kind === 'keyword' || (!item.kind && !isQuestionText(item.content)),
    8,
  )
  return previewProblemList(
    [...explicitKeywords, ...problemKeywords, ...fallbackKeywordList(child)],
    () => true,
    8,
  )
}

const next = () => {
  if (loading.value) return
  loading.value = true
  setTimeout(() => {
    loading.value = false
  }, 100)
}

const editHandle = (item: any, cIndex: number) => {
  // 计算实际索引，考虑分页
  currentCIndex.value = cIndex
  // currentCIndex.value = cIndex + page_size.value * (current_page.value - 1)
  // console.log('Edit index:', cIndex, page_size.value, current_page.value, currentCIndex.value)
  EditParagraphDialogRef.value.open(item)
}

const updateContent = (data: any) => {
  const new_value = [...props.modelValue]
  if (
    props.isConnect &&
    data.title &&
    !data?.problem_list.some((item: any) => item.content === data.title.trim())
  ) {
    data['problem_list'].push({
      content: data.title.trim(),
      kind: 'question',
    })
  }
  new_value[currentCIndex.value] = cloneDeep(data)
  emit('update:modelValue', new_value)

  // 更新本地列表
  const localIndex = currentCIndex.value - page_size.value * (current_page.value - 1)
  if (localIndex >= 0 && localIndex < localParagraphList.value.length) {
    localParagraphList.value[localIndex] = cloneDeep(data)
  }
}

const deleteHandle = (item: any, cIndex: number) => {
  MsgConfirm(
    `${t('views.paragraph.delete.confirmTitle')}${item.title || '-'} ?`,
    t('views.paragraph.delete.confirmMessage'),
    {
      confirmButtonText: t('common.confirm'),
      confirmButtonClass: 'danger',
    },
  )
    .then(() => {
      const new_value = [...props.modelValue]
      new_value.splice(cIndex, 1)
      emit('update:modelValue', new_value)

      // 更新本地列表
      localParagraphList.value.splice(cIndex, 1)
      // 如果当前页删除完了，从总数据中再取一条添加到末尾
      if (props.modelValue.length > localParagraphList.value.length * current_page.value) {
        const nextItem = props.modelValue[localParagraphList.value.length * current_page.value]
        if (nextItem) {
          localParagraphList.value.push(nextItem)
        }
      }
    })
    .catch(() => {})
}
</script>
<style lang="scss" scoped>
.paragraph-preview-card {
  position: relative;

  .related-preview {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .related-preview__label {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }

  .related-preview__tag {
    max-width: 100%;
    height: auto;
    align-items: flex-start;
    white-space: normal;
  }

  .related-preview__tag-text {
    display: inline;
    max-width: none;
    overflow: visible;
    text-overflow: clip;
    vertical-align: initial;
    white-space: normal;
    word-break: break-word;
  }

  .mk-sticky {
    height: 0;
    position: sticky;
    right: 0;
    top: 12px;
    overflow: inherit;
    z-index: 10;
  }
  .paragraph-box-operation {
    position: absolute;
    right: -10px;
    top: -20px;
    overflow: inherit;
    z-index: 10;
  }
}
</style>
