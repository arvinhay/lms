<template>
	<FrappeUIProvider>
		<Layout
			class="isolate text-p-base"
			:class="{ 'rea-lms-theme': theme === 'rea' }"
		>
			<router-view />
		</Layout>
		<InstallPrompt v-if="isMobile && !settings.data?.disable_pwa" />
		<Dialogs />
	</FrappeUIProvider>
</template>
<script setup>
import { FrappeUIProvider } from 'frappe-ui'
import { Dialogs } from '@/utils/dialogs'
import { computed, onUnmounted, ref } from 'vue'
import { useScreenSize } from './utils/composables'
import { useSettings } from '@/stores/settings'
import { useRouter } from 'vue-router'
import DesktopLayout from './components/Layouts/DesktopLayout.vue'
import MobileLayout from './components/Layouts/MobileLayout.vue'
import NoSidebarLayout from './components/Layouts/NoSidebarLayout.vue'
import InstallPrompt from './components/InstallPrompt.vue'
import { applyTheme, theme } from '@/utils/theme'

const { isMobile } = useScreenSize()
const router = useRouter()
const noSidebar = ref(false)
const { settings } = useSettings()

applyTheme(theme.value)

router.beforeEach((to, from, next) => {
	if (to.query.fromLesson || to.path === '/persona') {
		noSidebar.value = true
	} else {
		noSidebar.value = false
	}
	next()
})

const Layout = computed(() => {
	if (noSidebar.value) {
		return NoSidebarLayout
	}
	if (isMobile.value) {
		return MobileLayout
	}
	return DesktopLayout
})

onUnmounted(() => {
	noSidebar.value = false
})
</script>
