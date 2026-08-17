import { createApp } from 'vue'
import 'leaflet/dist/leaflet.css'
import './style.css'
import App from './App.vue'

/* 滾動進場動畫：v-reveal / v-reveal="{ delay: 120 }"
   元素進入視窗時加上 .reveal-in，只觸發一次。 */
const io = new IntersectionObserver(
  (entries) => {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.classList.add('reveal-in')
        io.unobserve(e.target)
      }
    }
  },
  { threshold: 0.12, rootMargin: '0px 0px -48px 0px' },
)

const reveal = {
  mounted(el, binding) {
    el.classList.add('reveal')
    const delay = binding.value?.delay
    if (delay) el.style.transitionDelay = `${delay}ms`
    io.observe(el)
  },
  unmounted(el) {
    io.unobserve(el)
  },
}

createApp(App).directive('reveal', reveal).mount('#app')
