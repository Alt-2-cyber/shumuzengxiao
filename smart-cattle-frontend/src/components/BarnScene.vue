<template>
  <div ref="container" class="scene-box">
    <div class="scene-overlay">
      <strong>3D 牛舍态势</strong>
      <div class="muted">绿色：正常  金色：观察  红色：告警</div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'

const props = defineProps({
  risks: { type: Array, default: () => [] }
})

const container = ref(null)
let renderer
let scene
let camera
let frameId
let herd = []

function makeCow(x, z, color) {
  const group = new THREE.Group()
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(1.35, 0.55, 0.62),
    new THREE.MeshStandardMaterial({ color, roughness: 0.75 })
  )
  body.position.y = 0.6
  const head = new THREE.Mesh(
    new THREE.BoxGeometry(0.45, 0.38, 0.42),
    new THREE.MeshStandardMaterial({ color: 0x2e2119, roughness: 0.8 })
  )
  head.position.set(0.82, 0.68, 0)
  const legMaterial = new THREE.MeshStandardMaterial({ color: 0x261d16, roughness: 0.9 })
  const legs = [-0.42, 0.42].flatMap((lx) => [-0.2, 0.2].map((lz) => {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.48, 0.12), legMaterial)
    leg.position.set(lx, 0.24, lz)
    return leg
  }))
  group.add(body, head, ...legs)
  group.position.set(x, 0, z)
  group.rotation.y = Math.random() * Math.PI * 2
  group.userData.baseY = Math.random() * 1.5
  return group
}

function riskColor(index) {
  const risk = props.risks[index % Math.max(props.risks.length, 1)]
  const level = risk?.level || risk?.riskLevel
  if (level === 'URGENT') return 0xa83228
  if (level === 'WARNING') return 0xb64235
  if (level === 'OBSERVE') return 0xb37a22
  const palette = [0x3c6a4d, 0x2f5b3d, 0x48744a, 0x315e59]
  return palette[index % palette.length]
}

function init() {
  const width = container.value.clientWidth
  const height = container.value.clientHeight
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xdfe8df)
  scene.fog = new THREE.Fog(0xdfe8df, 9, 18)

  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
  camera.position.set(5.8, 5.2, 7.4)
  camera.lookAt(0, 0, 0)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(width, height)
  renderer.shadowMap.enabled = true
  container.value.appendChild(renderer.domElement)

  const ambient = new THREE.HemisphereLight(0xffffff, 0xb7c5b7, 1.5)
  scene.add(ambient)
  const sun = new THREE.DirectionalLight(0xffffff, 2.1)
  sun.position.set(3, 8, 4)
  sun.castShadow = true
  scene.add(sun)

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(14, 10),
    new THREE.MeshStandardMaterial({ color: 0xbac8b3, roughness: 0.9 })
  )
  floor.rotation.x = -Math.PI / 2
  floor.receiveShadow = true
  scene.add(floor)

  const railMaterial = new THREE.MeshStandardMaterial({ color: 0x53675a, roughness: 0.75 })
  for (let z of [-3.4, 0, 3.4]) {
    const rail = new THREE.Mesh(new THREE.BoxGeometry(12, 0.12, 0.12), railMaterial)
    rail.position.set(0, 0.78, z)
    scene.add(rail)
  }
  for (let x = -5.5; x <= 5.5; x += 1.6) {
    const post = new THREE.Mesh(new THREE.BoxGeometry(0.12, 1.3, 0.12), railMaterial)
    post.position.set(x, 0.65, -3.4)
    scene.add(post)
  }

  herd = [
    makeCow(-4, -1.5, riskColor(0)),
    makeCow(-2.4, 1.6, riskColor(1)),
    makeCow(-0.6, -0.4, riskColor(2)),
    makeCow(1.4, 1.8, riskColor(3)),
    makeCow(3.2, -1.2, riskColor(4)),
    makeCow(4.5, 1.0, riskColor(5))
  ]
  herd.forEach((cow) => scene.add(cow))

  window.addEventListener('resize', resize)
  animate()
}

function resize() {
  if (!renderer || !container.value) return
  const width = container.value.clientWidth
  const height = container.value.clientHeight
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

function animate(time = 0) {
  herd.forEach((cow, index) => {
    cow.position.y = Math.sin(time * 0.0015 + cow.userData.baseY) * 0.03
    cow.rotation.y += index % 2 === 0 ? 0.001 : -0.0008
  })
  renderer.render(scene, camera)
  frameId = requestAnimationFrame(animate)
}

onMounted(init)
onBeforeUnmount(() => {
  cancelAnimationFrame(frameId)
  window.removeEventListener('resize', resize)
  renderer?.dispose()
})

watch(() => props.risks, () => {
  herd.forEach((cow, index) => {
    const body = cow.children[0]
    body.material.color.setHex(riskColor(index))
  })
}, { deep: true })
</script>
