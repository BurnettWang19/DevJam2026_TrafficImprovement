import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { viteStaticCopy } from 'vite-plugin-static-copy'

const cesiumSource = fileURLToPath(
  new URL('./node_modules/cesium/Build/Cesium', import.meta.url),
)
const cesiumBaseUrl = 'cesiumStatic'
const cesiumDirectories = ['Workers', 'ThirdParty', 'Assets', 'Widgets']

export default defineConfig({
  define: {
    CESIUM_BASE_URL: JSON.stringify(`/${cesiumBaseUrl}/`),
  },
  plugins: [
    vue(),
    viteStaticCopy({
      // v4 preserves source paths. Strip the common
      // node_modules/cesium/Build/Cesium/<directory> prefix while retaining
      // nested files such as Assets/Textures and ThirdParty/Workers.
      targets: cesiumDirectories.map((directory) => ({
        src: `${cesiumSource}/${directory}/**/*`,
        dest: `${cesiumBaseUrl}/${directory}`,
        rename: { stripBase: 5 },
      })),
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      // 前端一律打 /api，由 vite 轉給 FastAPI，省掉 CORS 與硬編網址
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
