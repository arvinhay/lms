<template>
	<div class="rea-nosidebar-layout relative flex h-full flex-col">
		<div class="h-full flex-1">
			<div class="rea-nosidebar-shell flex h-screen text-base bg-surface-white">
				<div
					class="rea-nosidebar-scroll w-full overflow-auto"
					id="scrollContainer"
				>
					<slot />
				</div>
			</div>
		</div>
	</div>
</template>
