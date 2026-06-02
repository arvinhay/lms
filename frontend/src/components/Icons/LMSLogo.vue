<template>
	<img
		:src="logoUrl"
		alt="Refugee Education Australia"
		class="object-contain"
	/>
</template>

<script setup>
import { computed } from 'vue'
import { sessionStore } from '@/stores/session'

const { brand } = sessionStore()

const logoUrl = computed(() => {
	return brand.logo?.file_url || '/assets/lms/frontend/rea-logo.png'
})
</script>
