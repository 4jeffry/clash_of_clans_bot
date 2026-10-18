import { ref, watchEffect } from 'vue'

const isDark = ref(localStorage.getItem('niki_theme') === 'dark')

export function useTheme() {
  function toggleTheme() {
    isDark.value = !isDark.value
  }

  watchEffect(() => {
    const root = document.documentElement
    if (isDark.value) {
      root.classList.add('dark')
      localStorage.setItem('niki_theme', 'dark')
    } else {
      root.classList.remove('dark')
      localStorage.setItem('niki_theme', 'light')
    }
  })

  return { isDark, toggleTheme }
}
