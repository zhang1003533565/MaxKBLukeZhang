import { useLocalStorage } from '@vueuse/core'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { i18n, langCode, localeConfigKey, normalizeLocale } from '@/locales/index'

export function useLocale() {
  const { locale } = useI18n({ useScope: 'global' })
  function changeLocale(lang: string) {
    const normalizedLang = normalizeLocale(lang)
    // 如果切换的语言不在对应语言文件里则默认为英文
    if (!langCode.includes(normalizedLang)) {
      locale.value = 'en-US'
      useLocalStorage(localeConfigKey, 'en-US').value = 'en-US'
      return
    }

    locale.value = normalizedLang
    useLocalStorage(localeConfigKey, 'en-US').value = normalizedLang
  }

  const getComponentsLocale = computed(() => {
    const localeMessage = i18n.global.getLocaleMessage(locale.value) as Record<string, any>
    return localeMessage.componentsLocale
  })

  return {
    changeLocale,
    getComponentsLocale,
    locale,
  }
}
