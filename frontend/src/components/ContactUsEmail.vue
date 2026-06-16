<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Contact Us'),
			size: 'md',
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<FormControl
					v-model="subject"
					:label="__('Subject')"
					type="text"
					:required="true"
				/>
				<div>
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Message') }}
						<span class="text-ink-red-3">*</span>
					</div>
					<TextEditor
						:key="editorKey"
						:fixedMenu="true"
						@change="(val) => (message = val)"
						editorClass="prose-sm py-2 px-2 min-h-[200px] border-outline-gray-2 hover:border-outline-gray-3 rounded-b-md bg-surface-gray-3"
					/>
				</div>
			</div>
		</template>
		<template #actions="{ close }">
			<div class="pb-5 float-end">
				<Button
					variant="solid"
					:loading="sending"
					:disabled="sending"
					@click="sendMail(close)"
				>
					{{ __('Send') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { Button, call, Dialog, FormControl, TextEditor, toast } from 'frappe-ui'
import { ref } from 'vue'

const show = defineModel<boolean>({ required: true, default: false })
const subject = ref('')
const message = ref('')
const sending = ref(false)
const editorKey = ref(0)

const sendMail = (close: Function) => {
	if (!subject.value.trim()) {
		toast.error(__('Please enter a subject'))
		return
	}
	if (!hasMessage(message.value)) {
		toast.error(__('Please enter a message'))
		return
	}

	sending.value = true
	call('lms.lms.api.send_contact_us_enquiry', {
		subject: subject.value,
		message: message.value,
		page_url: window.location.href,
	})
		.then(() => {
			toast.success(__('Enquiry sent successfully'))
			close()
			subject.value = ''
			message.value = ''
			editorKey.value += 1
		})
		.catch(() => {
			toast.error(__('Failed to send enquiry'))
		})
		.finally(() => {
			sending.value = false
		})
}

const hasMessage = (html: string) => {
	const text = (html || '')
		.replace(/<[^>]*>/g, '')
		.replace(/&nbsp;/g, ' ')
		.trim()
	return Boolean(text)
}
</script>
