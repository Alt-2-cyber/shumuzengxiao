import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'intro', component: () => import('../views/IntroView.vue') },
  { path: '/dashboard', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
  { path: '/environment', name: 'environment', component: () => import('../views/EnvironmentView.vue') },
  { path: '/health', name: 'health', component: () => import('../views/HealthView.vue') },
  { path: '/clinical', redirect: '/health' },
  { path: '/vision', name: 'vision', component: () => import('../views/VisionView.vue') },
  { path: '/audio', name: 'audio', component: () => import('../views/AudioView.vue') },
  { path: '/behavior', name: 'behavior', component: () => import('../views/BehaviorView.vue') },
  { path: '/devices', name: 'devices', component: () => import('../views/DevicesView.vue') },
  { path: '/models', name: 'models', component: () => import('../views/ModelsView.vue') }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
