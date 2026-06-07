<template>
	<Dialog
		v-model="show"
		:options="{
			title: dialogTitle,
		}"
	>
		<template #body-content>
			<div class="text-p-base">
				<div
					v-if="!uploadedCourseFile"
					@dragover.prevent
					@drop.prevent="(e) => uploadFile(e)"
					class="h-[120px] flex flex-col items-center justify-center bg-surface-gray-1 border border-dashed border-outline-gray-3 rounded-md"
				>
					<div v-if="!uploading" class="w-4/5 text-center">
						<UploadCloud
							class="size-6 stroke-1.5 text-ink-gray-6 mx-auto mb-2.5"
						/>
						<input
							ref="fileInput"
							type="file"
							class="hidden"
							:accept="acceptedExtension"
							@change="(e) => uploadFile(e)"
						/>
						<div class="leading-5 text-ink-gray-9">
							{{ dropzoneLabel }}
							<span
								@click="openFileSelector"
								class="cursor-pointer font-semibold hover:underline"
							>
								{{ __('Device') }}
							</span>
						</div>
						<div class="mt-1 text-sm text-ink-gray-6">
							{{ uploadLimitLabel }}
						</div>
					</div>
					<div
						v-else-if="uploading"
						class="w-fit bg-surface-white border rounded-md p-2 my-4"
					>
						<div class="space-y-2">
							<div class="font-medium">
								{{ uploadingFile.name }}
							</div>
							<div class="text-ink-gray-6">
								{{ convertToMB(uploaded) }} of {{ convertToMB(total) }}
							</div>
						</div>
						<div class="w-full bg-surface-gray-1 h-1 rounded-full mt-3">
							<div
								class="bg-surface-gray-7 h-1 rounded-full transition-all duration-500 ease-in-out"
								:style="`width: ${uploadProgress}%`"
							></div>
						</div>
					</div>
				</div>
				<div
					v-else-if="uploadedCourseFile"
					class="h-[120px] flex items-center justify-center bg-surface-gray-1 border border-dashed border-outline-gray-3 rounded-md"
				>
					<div
						class="w-fit bg-surface-white border rounded-md p-2 flex items-center justify-between gap-x-4 mx-5"
					>
						<div class="space-y-2">
							<div class="font-medium leading-5 text-ink-gray-9">
								{{ uploadedCourseFile.file_name || uploadedCourseFile.name }}
							</div>
							<div v-if="uploadedCourseFile.file_size" class="text-ink-gray-6">
								{{ convertToMB(uploadedCourseFile.file_size) }}
							</div>
						</div>
						<Trash2
							class="size-4 stroke-1.5 text-ink-red-3 cursor-pointer"
							@click="deleteFile"
						/>
					</div>
				</div>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end">
				<Button variant="solid" @click="importCourse">
					{{ __('Import') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { Button, call, Dialog, FileUploadHandler, toast } from 'frappe-ui'
import { computed, ref } from 'vue'
import { Trash2, UploadCloud } from 'lucide-vue-next'
import { useRouter } from 'vue-router'

const fileInput = ref<HTMLInputElement | null>(null)
const show = defineModel<boolean>({ required: true, default: false })
const props = withDefaults(
	defineProps<{
		mode?: 'zip' | 'imscc'
	}>(),
	{
		mode: 'zip',
	}
)
const uploadedCourseFile = ref<any | null>(null)
const uploaded = ref(0)
const total = ref(0)
const uploading = ref(false)
const uploadingFile = ref<any | null>(null)
const router = useRouter()
const MAX_COURSE_UPLOAD_SIZE_MB = 512
const MAX_COURSE_UPLOAD_SIZE_BYTES = MAX_COURSE_UPLOAD_SIZE_MB * 1024 * 1024

const openFileSelector = () => {
	fileInput.value?.click()
}

const isIMSCC = computed(() => props.mode === 'imscc')

const acceptedExtension = computed(() => (isIMSCC.value ? '.imscc' : '.zip'))

const dialogTitle = computed(() =>
	isIMSCC.value
		? __('Import Course from IMSCC (Canvas)')
		: __('Import Course from ZIP')
)

const dropzoneLabel = computed(() =>
	isIMSCC.value
		? __('Drag and drop an IMSCC file, or upload from your')
		: __('Drag and drop a ZIP file, or upload from your')
)

const uploadLimitLabel = computed(() =>
	__('Maximum file size: {0} MB', [MAX_COURSE_UPLOAD_SIZE_MB])
)

const uploadProgress = computed(() => {
	if (total.value === 0) return 0
	return Math.floor((uploaded.value / total.value) * 100)
})

const extractFile = (e: Event): File | null => {
	const inputFiles = (e.target as HTMLInputElement)?.files
	const dt = (e as DragEvent).dataTransfer?.files

	return inputFiles?.[0] || dt?.[0] || null
}

const validateFile = (file: File) => {
	const extension = file.name.split('.').pop()?.toLowerCase()
	const expectedExtension = isIMSCC.value ? 'imscc' : 'zip'
	if (extension !== expectedExtension) {
		const message = isIMSCC.value
			? __('Please upload a valid IMSCC file.')
			: __('Please upload a valid ZIP file.')
		toast.error(message)
		console.error(message)
		return false
	}

	if (file.size > MAX_COURSE_UPLOAD_SIZE_BYTES) {
		toast.error(
			__('The selected file is larger than the {0} MB upload limit.', [
				MAX_COURSE_UPLOAD_SIZE_MB,
			])
		)
		return false
	}

	return true
}

const getUploadErrorMessage = (error: any) => {
	const status = error?.status || error?.statusCode || error?.xhr?.status
	if (status === 413) {
		return __(
			'The server rejected this file because it exceeds the configured upload limit.'
		)
	}

	return error?.message || __('File upload failed. Please try again.')
}

const uploadFile = (e: Event) => {
	const file = extractFile(e)
	if (!file) return

	if (!validateFile(file)) return

	uploadingFile.value = file
	const uploader = new FileUploadHandler()
	let uploadErrorShown = false
	const showUploadError = (error: any) => {
		if (uploadErrorShown) return
		uploadErrorShown = true
		toast.error(getUploadErrorMessage(error))
	}

	uploader.on('start', () => {
		uploading.value = true
	})

	uploader.on('progress', (data: { uploaded: number; total: number }) => {
		uploaded.value = data.uploaded
		total.value = data.total
	})

	uploader.on('error', (error: any) => {
		uploading.value = false
		showUploadError(error)
		console.error('File upload error:', error)
	})

	uploader.on('finish', () => {
		uploading.value = false
	})
	uploader
		.upload(file, {
			private: 1,
		})
		.then((data: any) => {
			uploadedCourseFile.value = data
		})
		.catch((error: any) => {
			console.error('File upload error:', error)
			showUploadError(error)
			uploading.value = false
			uploadingFile.value = null
			uploaded.value = 0
			total.value = 0
		})
}

const importCourse = () => {
	if (!uploadedCourseFile.value) return
	const method = isIMSCC.value
		? 'lms.lms.api.import_course_from_imscc'
		: 'lms.lms.api.import_course_from_zip'
	const args = isIMSCC.value
		? { imscc_file_path: uploadedCourseFile.value.file_url }
		: { zip_file_path: uploadedCourseFile.value.file_url }

	call(method, args)
		.then((data: any) => {
			toast.success('Course imported successfully!')
			show.value = false
			deleteFile()
			router.push({
				name: 'CourseDetail',
				params: { courseName: data },
			})
		})
		.catch((error: any) => {
			toast.error('Error importing course: ' + error.message)
			console.error('Error importing course:', error)
		})
}

const deleteFile = () => {
	uploadedCourseFile.value = null
}

const convertToMB = (bytes: number) => {
	return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}
</script>
