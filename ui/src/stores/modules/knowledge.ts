import { defineStore } from 'pinia'
import type { knowledgeData } from '@/api/type/knowledge'
import type { UploadUserFile } from 'element-plus'
import { type Ref } from 'vue'
import knowledgeApi from '@/api/knowledge/knowledge'

export interface knowledgeStateTypes {
  baseInfo: knowledgeData | null
  documentsType: string
  documentsFiles: UploadUserFile[]
  knowledgeList: any[]
}

const useKnowledgeStore = defineStore('knowledge', {
  state: (): knowledgeStateTypes => ({
    baseInfo: null,
    documentsType: '',
    documentsFiles: [],
    knowledgeList: [],
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
  },
})

export default useKnowledgeStore
