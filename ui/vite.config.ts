import {fileURLToPath, URL} from 'node:url'
import type {ProxyOptions} from 'vite'
import {defineConfig, loadEnv} from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import DefineOptions from 'unplugin-vue-define-options/vite'
import path from 'path'
import {createHtmlPlugin} from 'vite-plugin-html'
import fs from 'fs'
// import vueDevTools from 'vite-plugin-vue-devtools'
const envDir = './env'
// 自定义插件：重命名入口文件
const renameHtmlPlugin = (outDir: string, entry: string) => {
  return {
    name: 'rename-html',
    closeBundle: () => {
      const buildDir = path.resolve(__dirname, outDir)
      const oldFile = path.join(buildDir, entry)
      const newFile = path.join(buildDir, 'index.html')

      // 检查文件是否存在
      if (fs.existsSync(oldFile)) {
        // 删除已存在的 index.html
        if (fs.existsSync(newFile)) {
          fs.unlinkSync(newFile)
        }
        // 重命名文件
        fs.renameSync(oldFile, newFile)
      }
    },
  }
}
// https://vite.dev/config/
export default defineConfig((conf: any) => {
  const mode = conf.mode
  const ENV = loadEnv(mode, envDir)
  const isChatMode = mode === 'chat'
  const entry = ENV.VITE_ENTRY || (isChatMode ? 'chat.html' : 'admin.html')
  const basePath = ENV.VITE_BASE_PATH || (isChatMode ? '/chat/' : '/admin/')
  const appPort = ENV.VITE_APP_PORT || (isChatMode ? '3001' : '3000')
  const backendPort = ENV.VITE_BACKEND_PORT || process.env.VITE_BACKEND_PORT || '8082'
  const proxyConf: Record<string, string | ProxyOptions> = {}
  proxyConf['/admin/api'] = {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
  }
  proxyConf['/chat/api'] = {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
  }
  proxyConf['/openapi'] = {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
  }
  proxyConf['/doc'] = {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(basePath, '/'),
  }
  proxyConf['/schema'] = {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(basePath, '/'),
  }
  proxyConf['/static'] = {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(basePath, '/'),
  }

  // 前端静态资源转发到本身
  proxyConf[`^${basePath}.+\/oss\/file\/.*$`] = {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
  }
  // 前端静态资源转发到本身
  proxyConf[`^${basePath}oss\/file\/.*$`] = {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
  }
  proxyConf[`^${basePath}oss\/get_url\/.*$`] = {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
  }
  // 前端静态资源转发到本身
  proxyConf[basePath] = {
    target: `http://127.0.0.1:${appPort}`,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(basePath, '/'),
  }

  return {
    preflight: false,
    lintOnSave: false,
    base: './',
    envDir: envDir,
    plugins: [
      vue(),
      vueJsx(),
      DefineOptions(),
      createHtmlPlugin({template: entry}),
      renameHtmlPlugin(`dist${basePath}`, entry),
    ],
    server: {
      cors: true,
      host: '0.0.0.0',
      port: Number(appPort),
      strictPort: true,
      proxy: proxyConf,
    },
    build: {
      outDir: `dist${basePath}`,
      emptyOutDir: false,
      target: 'es2022',
      rollupOptions: {
        input: entry,
      },
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
  }
})
