function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

const REVEAL_SELECTOR = [
  '.intro-hero',
  '.edition-band',
  '.edition-scroll',
  '.edition-scroll-heading',
  '.edition-step',
  '.card',
  '.feature-card',
  '.release-card',
  '.sensor-tile',
  '.event-row',
  '.control-state',
  '.flow-step',
  '.pipeline-step',
  '.deploy-grid > div'
].join(', ')

const TILT_SELECTOR = [
  '.card',
  '.feature-card',
  '.release-card',
  '.edition-visual',
  '.edge-card',
  '.sensor-tile',
  '.model-metrics div'
].join(', ')

const MAGNETIC_SELECTOR = [
  '.intro-primary',
  '.intro-secondary',
  '.button',
  '.command-button',
  '.icon-button'
].join(', ')

function setupPointerGlow() {
  const root = document.documentElement
  let frame = 0

  function move(event) {
    if (frame) return
    frame = window.requestAnimationFrame(() => {
      root.style.setProperty('--pointer-x', `${event.clientX}px`)
      root.style.setProperty('--pointer-y', `${event.clientY}px`)
      frame = 0
    })
  }

  window.addEventListener('pointermove', move, { passive: true })
  return () => {
    window.removeEventListener('pointermove', move)
    if (frame) window.cancelAnimationFrame(frame)
  }
}

function setupScrollProgress() {
  const root = document.documentElement
  let frame = 0

  function update() {
    const scrollable = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1)
    root.style.setProperty('--scroll-progress', `${clamp(window.scrollY / scrollable, 0, 1).toFixed(4)}`)
    frame = 0
  }

  function requestUpdate() {
    if (!frame) frame = window.requestAnimationFrame(update)
  }

  requestUpdate()
  window.addEventListener('scroll', requestUpdate, { passive: true })
  window.addEventListener('resize', requestUpdate)

  return () => {
    window.removeEventListener('scroll', requestUpdate)
    window.removeEventListener('resize', requestUpdate)
    if (frame) window.cancelAnimationFrame(frame)
  }
}

function setupReveal() {
  const targets = [...document.querySelectorAll(REVEAL_SELECTOR)]
  const visibleTargets = new Set()

  function markVisible(target) {
    target.classList.add('is-visible')
    visibleTargets.add(target)
  }

  targets.forEach((target, index) => {
    target.classList.add('reveal-ready')
    target.style.setProperty('--reveal-delay', `${Math.min(index * 38, 260)}ms`)

    const rect = target.getBoundingClientRect()
    if (rect.top < window.innerHeight && rect.bottom > 0) {
      markVisible(target)
    }
  })

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        markVisible(entry.target)
        observer.unobserve(entry.target)
      }
    })
  }, {
    rootMargin: '18% 0px 18% 0px',
    threshold: 0.01
  })

  targets.forEach((target) => {
    if (!visibleTargets.has(target)) observer.observe(target)
  })
  return () => observer.disconnect()
}

function setupParallax() {
  const layers = [...document.querySelectorAll('[data-depth]')]
  let frame = 0

  function update() {
    const viewportHeight = window.innerHeight || 1
    layers.forEach((layer) => {
      const depth = Number(layer.dataset.depth || 0)
      const rect = layer.getBoundingClientRect()
      const progress = clamp((viewportHeight - rect.top) / (viewportHeight + Math.max(rect.height, 1)), 0, 1)
      const offset = (progress - 0.5) * depth * 90
      layer.style.transform = `translate3d(0, ${offset.toFixed(2)}px, 0) scale(${1 + Math.abs(depth) * 0.018})`
    })
    frame = 0
  }

  function requestUpdate() {
    if (!frame) frame = window.requestAnimationFrame(update)
  }

  requestUpdate()
  window.addEventListener('scroll', requestUpdate, { passive: true })
  window.addEventListener('resize', requestUpdate)

  return () => {
    window.removeEventListener('scroll', requestUpdate)
    window.removeEventListener('resize', requestUpdate)
    if (frame) window.cancelAnimationFrame(frame)
    layers.forEach((layer) => {
      layer.style.removeProperty('transform')
    })
  }
}

function setupTilt() {
  const cards = [...document.querySelectorAll(TILT_SELECTOR)]
  const cleanups = []

  cards.forEach((card) => {
    function move(event) {
      const rect = card.getBoundingClientRect()
      const x = (event.clientX - rect.left) / rect.width - 0.5
      const y = (event.clientY - rect.top) / rect.height - 0.5
      card.style.setProperty('--tilt-x', `${(-y * 5).toFixed(2)}deg`)
      card.style.setProperty('--tilt-y', `${(x * 5).toFixed(2)}deg`)
      card.style.setProperty('--shine-x', `${((x + 0.5) * 100).toFixed(2)}%`)
      card.style.setProperty('--shine-y', `${((y + 0.5) * 100).toFixed(2)}%`)
      card.classList.add('is-tilting')
    }

    function leave() {
      card.classList.remove('is-tilting')
      card.style.setProperty('--tilt-x', '0deg')
      card.style.setProperty('--tilt-y', '0deg')
      card.style.removeProperty('--shine-x')
      card.style.removeProperty('--shine-y')
    }

    card.addEventListener('pointermove', move, { passive: true })
    card.addEventListener('pointerleave', leave)
    cleanups.push(() => {
      card.removeEventListener('pointermove', move)
      card.removeEventListener('pointerleave', leave)
    })
  })

  return () => cleanups.forEach((cleanup) => cleanup())
}

function setupMagneticButtons() {
  const targets = [...document.querySelectorAll(MAGNETIC_SELECTOR)]
  const cleanups = []

  targets.forEach((target) => {
    function move(event) {
      const rect = target.getBoundingClientRect()
      const x = ((event.clientX - rect.left) / rect.width - 0.5) * 8
      const y = ((event.clientY - rect.top) / rect.height - 0.5) * 6
      target.style.setProperty('--magnet-x', `${x.toFixed(2)}px`)
      target.style.setProperty('--magnet-y', `${y.toFixed(2)}px`)
      target.classList.add('is-magnetic')
    }

    function leave() {
      target.classList.remove('is-magnetic')
      target.style.setProperty('--magnet-x', '0px')
      target.style.setProperty('--magnet-y', '0px')
    }

    target.addEventListener('pointermove', move, { passive: true })
    target.addEventListener('pointerleave', leave)
    cleanups.push(() => {
      target.removeEventListener('pointermove', move)
      target.removeEventListener('pointerleave', leave)
    })
  })

  return () => cleanups.forEach((cleanup) => cleanup())
}

function setupEditionScroll() {
  const story = document.querySelector('.edition-story')
  const steps = [...document.querySelectorAll('[data-edition-step]')]
  const visuals = [...document.querySelectorAll('[data-edition-visual]')]
  const dots = [...document.querySelectorAll('[data-edition-dot]')]

  if (!story || !steps.length || !visuals.length) {
    return () => {}
  }

  let frame = 0

  function setActive(index) {
    steps.forEach((step, stepIndex) => {
      step.classList.toggle('is-active', stepIndex === index)
      step.classList.toggle('is-before', stepIndex < index)
    })
    visuals.forEach((visual, visualIndex) => {
      visual.classList.toggle('is-active', visualIndex === index)
      visual.classList.toggle('is-before', visualIndex < index)
    })
    dots.forEach((dot, dotIndex) => {
      dot.classList.toggle('is-active', dotIndex === index)
    })
    story.style.setProperty('--edition-active', index)
  }

  function update() {
    const focusY = window.innerHeight * 0.48
    let activeIndex = 0
    let shortestDistance = Number.POSITIVE_INFINITY

    steps.forEach((step, index) => {
      const rect = step.getBoundingClientRect()
      const center = rect.top + rect.height * 0.5
      const distance = Math.abs(center - focusY)
      if (distance < shortestDistance) {
        shortestDistance = distance
        activeIndex = index
      }
    })

    setActive(activeIndex)
    frame = 0
  }

  function requestUpdate() {
    if (!frame) frame = window.requestAnimationFrame(update)
  }

  dots.forEach((dot, index) => {
    dot.addEventListener('click', () => {
      steps[index]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  })

  requestUpdate()
  window.addEventListener('scroll', requestUpdate, { passive: true })
  window.addEventListener('resize', requestUpdate)

  return () => {
    window.removeEventListener('scroll', requestUpdate)
    window.removeEventListener('resize', requestUpdate)
    if (frame) window.cancelAnimationFrame(frame)
  }
}

function setupPageEffects() {
  const cleanups = [
    setupReveal(),
    setupParallax(),
    setupTilt(),
    setupMagneticButtons(),
    setupEditionScroll()
  ]

  return () => cleanups.forEach((cleanup) => cleanup())
}

function setupDomRefresh(onRefresh) {
  let timer = 0

  function scheduleRefresh() {
    window.clearTimeout(timer)
    timer = window.setTimeout(onRefresh, 80)
  }

  const observer = new MutationObserver((mutations) => {
    const hasInsertedContent = mutations.some((mutation) => (
      mutation.type === 'childList'
      && [...mutation.addedNodes].some((node) => (
        node.nodeType === Node.ELEMENT_NODE
        && !node.closest?.('.route-fade-leave-active')
      ))
    ))

    if (hasInsertedContent) scheduleRefresh()
  })

  observer.observe(document.getElementById('app') || document.body, {
    childList: true,
    subtree: true
  })

  return () => {
    window.clearTimeout(timer)
    observer.disconnect()
  }
}

export function runPremiumEffects() {
  if (typeof window === 'undefined') {
    return {
      refresh() {},
      cleanup() {}
    }
  }

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduceMotion) {
    document.body.classList.add('prefers-reduced-motion')
    return {
      refresh() {},
      cleanup() {
        document.body.classList.remove('prefers-reduced-motion')
      }
    }
  }

  document.body.classList.add('has-premium-effects')

  let frame = 0
  let pageCleanup = setupPageEffects()

  function refresh() {
    if (frame) window.cancelAnimationFrame(frame)
    frame = window.requestAnimationFrame(() => {
      pageCleanup()
      pageCleanup = setupPageEffects()
      document.body.classList.add('effects-refreshed')
      window.setTimeout(() => document.body.classList.remove('effects-refreshed'), 360)
      frame = 0
    })
  }

  const cleanups = [
    setupPointerGlow(),
    setupScrollProgress(),
    setupDomRefresh(refresh)
  ]

  return {
    refresh,
    cleanup() {
      if (frame) window.cancelAnimationFrame(frame)
      pageCleanup()
      cleanups.forEach((cleanup) => cleanup())
      document.body.classList.remove('has-premium-effects', 'effects-refreshed')
    }
  }
}
