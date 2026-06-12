const qwenIcon =
  '<svg width="100%" height="100%" viewBox="0 0 50 50" xmlns="http://www.w3.org/2000/svg"><rect width="50" height="50" rx="10" fill="#165DFF"/><path d="M25 7 39.7 15.5V32.5L25 41 10.3 32.5V15.5L25 7Z" fill="#6AEAD4"/><path d="M25 13.2 34.3 18.6V29.4L25 34.8 15.7 29.4V18.6L25 13.2Z" fill="#725CFF"/><path d="M25 19.2 29.1 21.6V26.4L25 28.8 20.9 26.4V21.6L25 19.2Z" fill="#FFFFFF"/></svg>'

const xiaomiIcon =
  '<svg width="100%" height="100%" viewBox="0 0 50 50" xmlns="http://www.w3.org/2000/svg"><rect width="50" height="50" rx="10" fill="#FF6900"/><path d="M12 17.8C12 15.7 13.7 14 15.8 14H34.2C36.3 14 38 15.7 38 17.8V36H32.8V19.7C32.8 19.1 32.3 18.6 31.7 18.6H29.9V36H24.8V18.6H22.4V36H17.2V18.6H15.8C15.2 18.6 14.7 19.1 14.7 19.7V36H12V17.8Z" fill="#FFFFFF"/><circle cx="35.5" cy="10.8" r="2.3" fill="#FFFFFF"/></svg>'

const xfyunIcon =
  '<svg width="100%" height="100%" viewBox="0 0 50 50" xmlns="http://www.w3.org/2000/svg"><rect width="50" height="50" rx="10" fill="#EEF6FF"/><path d="M15 31.5C10.9 28.2 10.2 22.2 13.5 18.1C16.8 14 22.8 13.3 26.9 16.6L31.5 20.3C33.5 21.9 36.4 21.6 38 19.6C39.6 17.6 39.3 14.7 37.3 13.1L35.6 11.7" stroke="#1683FF" stroke-width="4" stroke-linecap="round"/><path d="M35 18.5C39.1 21.8 39.8 27.8 36.5 31.9C33.2 36 27.2 36.7 23.1 33.4L18.5 29.7C16.5 28.1 13.6 28.4 12 30.4C10.4 32.4 10.7 35.3 12.7 36.9L14.4 38.3" stroke="#FF4B4B" stroke-width="4" stroke-linecap="round"/></svg>'

const deepseekIcon =
  '<svg width="100%" height="100%" viewBox="0 0 50 50" xmlns="http://www.w3.org/2000/svg"><rect width="50" height="50" rx="10" fill="#EDF2FF"/><path d="M14 25C14 18.9 18.9 14 25 14H36L32 20H25C22.2 20 20 22.2 20 25C20 27.8 22.2 30 25 30H36L32 36H25C18.9 36 14 31.1 14 25Z" fill="#4D6BFE"/><path d="M27 22H39L35.5 27H27C25.3 27 24 28.3 24 30V36H18V30C18 25.6 21.6 22 27 22Z" fill="#6A8BFF"/></svg>'

export const providerList = [
  {
    provider: 'aliyun_bai_lian_model_provider',
    name: '通义千问（阿里云百炼）',
    icon: qwenIcon
  },
  {
    provider: 'model_xiaomi_mimo_provider',
    name: '小米 MiMo',
    icon: xiaomiIcon
  },
  {
    provider: 'model_xf_provider',
    name: '讯飞星火',
    icon: xfyunIcon
  },
  {
    provider: 'model_deepseek_provider',
    name: 'DeepSeek',
    icon: deepseekIcon
  }
]
