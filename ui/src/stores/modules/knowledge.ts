import { defineStore } from 'pinia'
import type { knowledgeData } from '@/api/type/knowledge'
import type { UploadUserFile } from 'element-plus'
import { type Ref } from 'vue'
import knowledgeApi from '@/api/knowledge/knowledge'

export type DocumentUploadDraftStatus = 'uploading' | 'parsing' | 'ready' | 'failed'

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
  form: {
    patterns: string[]
    limit: number
    with_filter: boolean
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

const useKnowledgeStore = defineStore('knowledge', {
  state: (): knowledgeStateTypes => ({
    baseInfo: null,
    documentsType: '',
    documentsFiles: [],
    knowledgeList: [],
    documentUploadDraft: null,
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
    },
    clearDocumentUploadDraft() {
      this.documentUploadDraft = null
    },
  },
})

export default useKnowledgeStore
