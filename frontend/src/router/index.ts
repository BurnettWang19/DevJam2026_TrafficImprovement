import { createRouter, createWebHistory } from 'vue-router'

import AnalyzeView from '../views/AnalyzeView.vue'
import HomeView from '../views/HomeView.vue'
import ResultView from '../views/ResultView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/analyze', name: 'analyze', component: AnalyzeView },
    { path: '/results', name: 'results', component: ResultView }
  ]
})
