import { del, get, post, put, request } from '@/request/index'
import type { Result } from '@/request/Result'
import type { Ref } from 'vue'

const prefix = '/system/openapi/keys'

const getKeyList: (params: any, loading?: Ref<boolean>) => Promise<Result<any[]>> = (
  params,
  loading,
) => {
  return get(prefix, params, loading)
}

const createKey: (data: any, loading?: Ref<boolean>) => Promise<Result<any>> = (data, loading) => {
  return post(prefix, data, undefined, loading)
}

const updateKey: (keyId: string, data: any, loading?: Ref<boolean>) => Promise<Result<any>> = (
  keyId,
  data,
  loading,
) => {
  return put(`${prefix}/${keyId}`, data, undefined, loading)
}

const deleteKey: (keyId: string, loading?: Ref<boolean>) => Promise<Result<boolean>> = (
  keyId,
  loading,
) => {
  return del(`${prefix}/${keyId}`, undefined, undefined, loading)
}

const callOpenAPI: (
  url: string,
  apiKey: string,
  options?: RequestInit,
) => Promise<Result<any>> = async (url, apiKey, options = {}) => {
  const headers = new Headers(options.headers || {})
  headers.set('Authorization', `Bearer ${apiKey}`)
  const response = await fetch(url, {
    ...options,
    headers,
  })
  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json') ? await response.json() : await response.text()
  if (response.ok || (typeof data === 'object' && data !== null && 'code' in data)) {
    return data
  }
  return {
    code: response.status,
    message: response.statusText || 'Request failed',
    data,
  }
}

const uploadDocument: (
  url: string,
  apiKey: string,
  formData: FormData,
) => Promise<Result<any>> = (url, apiKey, formData) => {
  return callOpenAPI(url, apiKey, {
    method: 'POST',
    body: formData,
  })
}

const getDocs: () => Promise<Result<any>> = () => {
  return request({
    url: `${window.location.origin}/openapi/knowledge/v1/docs`,
    method: 'get',
  }).then((response) => response.data)
}

export default {
  getKeyList,
  createKey,
  updateKey,
  deleteKey,
  callOpenAPI,
  uploadDocument,
  getDocs,
}
