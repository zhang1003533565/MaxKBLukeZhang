import { defineStore } from 'pinia'
import type { knowledgeData } from '@/api/type/knowledge'
import type { UploadUserFile } from 'element-plus'
import { type Ref } from 'vue'
import knowledgeApi from '@/api/knowledge/knowledge'

const DOCUMENT_UPLOAD_DRAFT_KEY = 'maxkb-document-upload-draft'

export type DocumentUploadDraftStatus =
  | 'uploading'
  | 'queued'
  | 'processing'
  | 'parsing'
  | 'ready'
  | 'failed'
  | 'cancelled'

export interface DocumentUploadDraft {
  key: string
  taskId: string
  status: DocumentUploadDraftStatus
  progress: number
  fileNames: string[]
  fileCount: number
  totalSize: number
  paragraphList: any[]
  checkedConnect: boolean
  radio: string
  startedByUser?: boolean
  backendTaskId?: string
  stage?: string
  processed?: number
  total?: number
  remaining?: number
  form: {
    patterns: string[]
    limit: number
    with_filter: boolean
    qa_parse_mode?: string
    llm_model_id: string
    vision_model_id: string
    quality_optimize?: boolean
  }
  message?: string
  updatedAt: number
  promise?: Promise<unknown>
}

export interface knowledgeStateTypes {
  baseInfo: knowledgeData | null
  documentsType: string
  documentsFiles: UploadUserFile[]
  knowledgeList: any[]
  documentUploadDraft: DocumentUploadDraft | null
}

function loadDocumentUploadDraft(): DocumentUploadDraft | null {
  if (typeof window === 'undefined') {
    return null
  }
  try {
    const value = window.sessionStorage.getItem(DOCUMENT_UPLOAD_DRAFT_KEY)
    return value ? JSON.parse(value) : null
  } catch {
    return null
  }
}

function saveDocumentUploadDraft(draft: DocumentUploadDraft | null) {
  if (typeof window === 'undefined') {
    return
  }
  if (!draft) {
    window.sessionStorage.removeItem(DOCUMENT_UPLOAD_DRAFT_KEY)
    return
  }
  const { promise: _promise, ...persistedDraft } = draft
  window.sessionStorage.setItem(DOCUMENT_UPLOAD_DRAFT_KEY, JSON.stringify(persistedDraft))
}

const useKnowledgeStore = defineStore('knowledge', {
  state: (): knowledgeStateTypes => ({
    baseInfo: null,
    documentsType: '',
    documentsFiles: [],
    knowledgeList: [],
    documentUploadDraft: loadDocumentUploadDraft(),
  }),
  actions: {
    saveBaseInfo(info: knowledgeData | null) {
      this.baseInfo = info
    },
    saveDocumentsType(val: string) {
      this.documentsType = val
    },
    saveDocumentsFile(file: UploadUserFile[]) {
      this.documentsFiles = file
    },
    setKnowledgeList(list: any[]) {
      this.knowledgeList = list
    },
    setDocumentUploadDraft(draft: DocumentUploadDraft) {
      this.documentUploadDraft = draft
      saveDocumentUploadDraft(draft)
    },
    patchDocumentUploadDraft(draft: Partial<DocumentUploadDraft>) {
      if (!this.documentUploadDraft) {
        return
      }
      this.documentUploadDraft = {
        ...this.documentUploadDraft,
        ...draft,
        updatedAt: Date.now(),
      }
      saveDocumentUploadDraft(this.documentUploadDraft)
    },
    clearDocumentUploadDraft() {
      this.documentUploadDraft = null
      saveDocumentUploadDraft(null)
    },
  },
})

export default useKnowledgeStore
