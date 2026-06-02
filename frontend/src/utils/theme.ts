import { computed, ref } from 'vue'

type LMSTheme = 'rea' | 'light' | 'dark'
type ColorMode = 'light' | 'dark'

const THEME_STORAGE_KEY = 'lms-theme'
const LEGACY_THEME_STORAGE_KEY = 'theme'

const themeOptions: { value: LMSTheme; label: string }[] = [
	{ value: 'rea', label: 'REA colours' },
	{ value: 'light', label: 'White' },
	{ value: 'dark', label: 'Black' },
]

const isLMSTheme = (value: string | null): value is LMSTheme => {
	return value === 'rea' || value === 'light' || value === 'dark'
}

const getThemeColorMode = (value: LMSTheme): ColorMode => {
	return value === 'dark' ? 'dark' : 'light'
}

const getInitialTheme = (): LMSTheme => {
	const storedTheme = localStorage.getItem(THEME_STORAGE_KEY)
	if (isLMSTheme(storedTheme)) return storedTheme

	const legacyTheme = localStorage.getItem(LEGACY_THEME_STORAGE_KEY)
	return legacyTheme === 'dark' ? 'dark' : 'rea'
}

const theme = ref<LMSTheme>(getInitialTheme())
const isDarkTheme = computed(() => getThemeColorMode(theme.value) === 'dark')

const toggleTheme = () => {
	const currentIndex = themeOptions.findIndex(
		(option) => option.value === theme.value
	)
	const nextIndex = currentIndex === themeOptions.length - 1 ? 0 : currentIndex + 1
	const newTheme = themeOptions[nextIndex].value
	applyTheme(newTheme)
}

const applyTheme = (value: LMSTheme) => {
	const newTheme = isLMSTheme(value) ? value : 'rea'
	const colorMode = getThemeColorMode(newTheme)

	document.documentElement.setAttribute('data-theme', colorMode)
	document.documentElement.setAttribute('data-lms-theme', newTheme)
	localStorage.setItem(THEME_STORAGE_KEY, newTheme)
	localStorage.setItem(LEGACY_THEME_STORAGE_KEY, colorMode)
	theme.value = newTheme
}

export {
	applyTheme,
	getThemeColorMode,
	isDarkTheme,
	theme,
	themeOptions,
	toggleTheme,
}
export type { LMSTheme }
