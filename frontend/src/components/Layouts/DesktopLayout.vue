<template>
	<div class="rea-desktop-layout flex h-screen w-screen">
		<div class="rea-sidebar-shell h-full border-e bg-surface-menu-bar">
			<AppSidebar />
		</div>
		<div
			class="rea-main-shell flex-1 flex flex-col h-full overflow-auto bg-surface-white"
		>
			<slot />
		</div>
	</div>
</template>
<script setup>
import AppSidebar from '@/components/Sidebar/AppSidebar.vue'
</script>
