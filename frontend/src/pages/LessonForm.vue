<template>
	<div class="">
		<div class="grid md:grid-cols-[75%,25%] h-screen">
			<div class="border-e">
				<header
					class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b overflow-hidden bg-surface-white px-3 py-2.5 sm:px-5"
				>
					<Breadcrumbs class="text-ellipsis" :items="breadcrumbs" />
					<div class="mt-3 flex items-center gap-2 md:mt-0">
						<Badge v-if="isDirty" theme="orange">
							{{ __('Unsaved changes') }}
						</Badge>
						<Button v-if="isDirty" @click="discardAndLeave">
							{{ __('Discard and Exit') }}
						</Button>
						<Button
							variant="solid"
							:loading="isSaving"
							@click="saveLesson({ showSuccessMessage: true })"
						>
							{{ __('Save') }}
						</Button>
					</div>
				</header>
				<div class="py-5">
					<div class="w-5/6 mx-auto space-y-5">
						<div class="grid grid-cols-2 gap-5">
							<FormControl
								v-model="lesson.title"
								:label="__('Title')"
								:required="true"
								autocomplete="off"
							/>
							<Switch
								v-model="lesson.include_in_preview"
								:label="__('Include in Preview')"
								:description="
									__(
										'If enabled, the lesson will also be accessible to users who are not enrolled in the course.'
									)
								"
							/>
						</div>
						<div
							class="rounded-md border border-outline-gray-2 bg-surface-white p-4"
						>
							<div
								class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
							>
								<div>
									<div class="text-sm font-medium text-ink-gray-8">
										{{ __('Lesson Format') }}
									</div>
									<div class="mt-1 text-sm text-ink-gray-5">
										{{ lessonFormatDescription }}
									</div>
								</div>
								<TabButtons
									:buttons="lessonFormatOptions"
									:model-value="lessonFormat"
									@update:modelValue="setLessonFormat"
									class="w-fit"
								/>
							</div>
						</div>
					</div>
					<div class="border-t mt-4">
						<div class="w-5/6 mx-auto pt-4">
							<div
								class="flex justify-between cursor-pointer"
								@click="
									() => {
										openInstructorEditor = !openInstructorEditor
									}
								"
							>
								<label class="block font-medium text-ink-gray-5 mb-1">
									{{ __('Instructor Notes') }}
								</label>
								<ChevronRight
									class="stroke-2 h-5 w-5 text-ink-gray-5 transform duration-200"
									:class="{
										'rotate-90': openInstructorEditor,
										'rtl:rotate-180': !openInstructorEditor,
									}"
								/>
							</div>
							<div
								v-show="openInstructorEditor"
								id="instructor-notes"
								class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal py-3"
							></div>
						</div>
					</div>
					<div class="border-t mt-4">
						<div class="w-5/6 mx-auto pt-4">
							<label class="block font-medium text-ink-gray-5 mb-1">
								{{ __('Content') }}
							</label>
							<div v-show="htmlBodyMode" class="space-y-4">
								<div
									class="flex flex-col gap-3 rounded-md border border-outline-gray-2 bg-surface-gray-1 p-3 sm:flex-row sm:items-center sm:justify-between"
								>
									<div class="text-sm text-ink-gray-6">
										{{
											__(
												'Preserved HTML keeps imported Canvas layout and media intact. Edit HTML only.'
											)
										}}
									</div>
									<TabButtons
										:buttons="htmlEditorTabs"
										v-model="htmlEditorTab"
										class="w-fit"
									/>
								</div>
								<div v-show="htmlEditorTab === 'edit'" class="space-y-3">
									<Code
										v-model="lesson.body"
										language="html"
										height="430px"
										max-height="620px"
										:show-border="true"
									/>
									<div class="flex items-center justify-between gap-3">
										<Button @click="checkHtmlLesson">
											{{ __('Check Lesson') }}
										</Button>
										<div class="text-sm text-ink-gray-5">
											{{ __('Use Preview before saving major edits.') }}
										</div>
									</div>
									<div
										v-if="htmlCheckRan"
										class="rounded-md border p-3 text-sm"
										:class="
											htmlCheckIssues.length
												? 'border-outline-gray-3 bg-surface-gray-1 text-ink-gray-8'
												: 'border-outline-gray-2 bg-surface-white text-ink-gray-8'
										"
									>
										<div class="font-medium">
											{{
												htmlCheckIssues.length
													? __('Review these HTML items')
													: __('No obvious HTML issues found')
											}}
										</div>
										<ul
											v-if="htmlCheckIssues.length"
											class="mt-2 list-disc ps-5"
										>
											<li v-for="issue in htmlCheckIssues" :key="issue">
												{{ issue }}
											</li>
										</ul>
									</div>
								</div>
								<div v-show="htmlEditorTab === 'preview'">
									<div class="mb-2 text-sm font-medium text-ink-gray-5">
										{{ __('Preview') }}
									</div>
									<div
										class="prose prose-sm max-w-none rounded-md border border-outline-gray-2 bg-surface-white p-4"
									>
										<LessonContent
											:content="lesson.body || ''"
											:youtube="lesson.youtube"
											:quiz-id="lesson.quiz_id"
										/>
									</div>
								</div>
							</div>
							<div
								v-show="!htmlBodyMode"
								id="content"
								class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal py-3"
							></div>
						</div>
					</div>
				</div>
			</div>
			<div class="">
				<div class="sticky top-0 p-5">
					<LessonHelp />
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import {
	Badge,
	Breadcrumbs,
	Button,
	createResource,
	FormControl,
	Switch,
	TabButtons,
	usePageMeta,
	toast,
} from 'frappe-ui'
import {
	computed,
	reactive,
	onMounted,
	inject,
	ref,
	onBeforeUnmount,
	nextTick,
	watch,
} from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRouter } from 'vue-router'
import { sessionStore } from '../stores/session'
import EditorJS from '@editorjs/editorjs'
import LessonHelp from '@/components/LessonHelp.vue'
import LessonContent from '@/components/LessonContent.vue'
import Code from '@/components/Controls/Code.vue'
import { ChevronRight } from 'lucide-vue-next'
import { getEditorTools, enablePlyr, sanitizeEditorJs } from '@/utils'
import { useOnboarding, useTelemetry } from 'frappe-ui/frappe'

const { brand } = sessionStore()
const editor = ref(null)
const instructorEditor = ref(null)
const user = inject('$user')
const openInstructorEditor = ref(false)
const htmlBodyMode = ref(false)
const lessonFormat = ref('native')
const htmlEditorTab = ref('edit')
const htmlCheckRan = ref(false)
const htmlCheckIssues = ref([])
const isDirty = ref(false)
const isHydrating = ref(true)
const isSaving = ref(false)
const router = useRouter()
const { capture } = useTelemetry()
const { updateOnboardingStep } = useOnboarding('learning')

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
	chapterNumber: {
		type: String,
		required: true,
	},
	lessonNumber: {
		type: String,
		required: true,
	},
})

onMounted(() => {
	if (!user.data?.is_moderator && !user.data?.is_instructor) {
		window.location.href = '/login'
	}
	capture('lesson_form_opened')
	editor.value = renderEditor('content')
	instructorEditor.value = renderEditor('instructor-notes')
	window.addEventListener('keydown', keyboardShortcut)
	window.addEventListener('beforeunload', handleBeforeUnload)
	enablePlyr()
})

const renderEditor = (holder) => {
	return new EditorJS({
		holder: holder,
		tools: getEditorTools(true),
		defaultBlock: 'markdown',
		i18n: {
			direction: document.documentElement.dir === 'rtl' ? 'rtl' : 'ltr',
		},
		onChange: async () => {
			enablePlyr()
			if (!isHydrating.value) isDirty.value = true
		},
	})
}

const lesson = reactive({
	title: '',
	include_in_preview: false,
	body: '',
	instructor_notes: '',
	content: '',
})

watch(
	() => [lesson.title, lesson.include_in_preview, lesson.body],
	() => {
		if (!isHydrating.value) isDirty.value = true
	}
)

const lessonFormatOptions = computed(() => [
	{
		label: __('Frappe Native'),
		value: 'native',
	},
	{
		label: __('Preserved HTML'),
		value: 'html',
	},
])

const htmlEditorTabs = computed(() => [
	{
		label: __('Edit HTML'),
		value: 'edit',
	},
	{
		label: __('Preview'),
		value: 'preview',
	},
])

const lessonFormatDescription = computed(() => {
	if (lessonFormat.value === 'html') {
		return __(
			'HTML lessons preserve imported Canvas styling and media. Changes are saved only when you press Save.'
		)
	}
	return __(
		'Native lessons use the standard Frappe lesson editor. Changes are saved only when you press Save.'
	)
})

const lessonDetails = createResource({
	url: 'lms.lms.utils.get_lesson_creation_details',
	params: {
		course: props.courseName,
		chapter: props.chapterNumber,
		lesson: props.lessonNumber,
	},
	auto: true,
	async onSuccess(data) {
		isHydrating.value = true
		if (data.lesson) {
			Object.keys(data.lesson).forEach((key) => {
				lesson[key] = data.lesson[key]
			})
			lesson.include_in_preview = data?.lesson?.include_in_preview
				? true
				: false
		}
		await Promise.all([addLessonContent(data), addInstructorNotes(data)])
		isDirty.value = false
		isHydrating.value = false
	},
})

const addLessonContent = async (data) => {
	const lessonData = data.lesson || {}
	setHtmlBodyMode(isImportedHtmlLesson(lessonData))
	if (htmlBodyMode.value) return

	await editor.value.isReady
	if (lessonData.content) {
		await editor.value.render(sanitizeEditorJs(JSON.parse(lessonData.content)))
	} else if (lessonData.body) {
		let blocks = convertToJSON(lessonData)
		await editor.value.render({
			blocks: blocks,
		})
	}
}

const setHtmlBodyMode = (enabled) => {
	htmlBodyMode.value = enabled
	lessonFormat.value = enabled ? 'html' : 'native'
	htmlEditorTab.value = enabled ? htmlEditorTab.value : 'edit'
	htmlCheckRan.value = false
	htmlCheckIssues.value = []
}

const setLessonFormat = async (format) => {
	if (format === lessonFormat.value) return

	if (format === 'html') {
		const hasNativeContent = await nativeEditorHasContent()
		if (
			hasNativeContent &&
			!window.confirm(
				__(
					'Switch to a Preserved HTML draft? Nothing changes until you press Save, and leaving without saving restores the current lesson.'
				)
			)
		) {
			return
		}
		setHtmlBodyMode(true)
		isDirty.value = true
		return
	}

	if (
		lesson.body?.trim() &&
		!window.confirm(
			__(
				'Switch to a Frappe Native draft? Saving may simplify preserved HTML styling. Leaving without saving restores the current HTML lesson.'
			)
		)
	) {
		return
	}

	setHtmlBodyMode(false)
	await nextTick()
	await renderBodyInNativeEditor()
	isDirty.value = true
}

const nativeEditorHasContent = async () => {
	if (lesson.content) return true
	if (!editor.value) return false

	try {
		await editor.value.isReady
		let outputData = await editor.value.save()
		outputData = removeEmptyBlocks(outputData)
		return outputData.blocks.some((block) => {
			if (block.type === 'paragraph') {
				return Boolean(block.data?.text?.trim())
			}
			return Object.keys(block.data || {}).some((key) => {
				let value = block.data[key]
				return Array.isArray(value) ? value.length : Boolean(value)
			})
		})
	} catch {
		return false
	}
}

const renderBodyInNativeEditor = async () => {
	if (!lesson.body || !editor.value) return
	await editor.value.isReady
	await editor.value.render({
		blocks: convertToJSON(lesson),
	})
}

const addInstructorNotes = async (data) => {
	const lessonData = data.lesson || {}
	await instructorEditor.value.isReady
	if (lessonData.instructor_content) {
		await instructorEditor.value.render(
			sanitizeEditorJs(JSON.parse(lessonData.instructor_content))
		)
	} else if (lessonData.instructor_notes) {
		let blocks = convertToJSON(lessonData)
		await instructorEditor.value.render({
			blocks: blocks,
		})
	}
}

const keyboardShortcut = (e) => {
	if (
		e.key === 's' &&
		(e.ctrlKey || e.metaKey) &&
		!e.target.classList.contains('ProseMirror')
	) {
		saveLesson({ showSuccessMessage: true })
		e.preventDefault()
	}
}

const confirmNavigation = () => {
	if (!isDirty.value) return true
	return window.confirm(
		__(
			'Leave without saving? Your draft changes will be discarded and the last saved lesson will remain unchanged.'
		)
	)
}

const handleBeforeUnload = (event) => {
	if (!isDirty.value) return
	event.preventDefault()
	event.returnValue = ''
}

const discardAndLeave = () => {
	if (
		!window.confirm(
			__(
				'Discard all unsaved changes and leave this lesson? The last saved version will remain unchanged.'
			)
		)
	) {
		return
	}

	isDirty.value = false
	if (lessonDetails.data?.lesson) {
		router.push({
			name: 'Lesson',
			params: {
				courseName: props.courseName,
				chapterNumber: props.chapterNumber,
				lessonNumber: props.lessonNumber,
			},
		})
		return
	}

	router.push({
		name: 'CourseDetail',
		params: { courseName: props.courseName },
		hash: '#settings',
	})
}

onBeforeRouteLeave(confirmNavigation)
onBeforeRouteUpdate(confirmNavigation)

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
	window.removeEventListener('beforeunload', handleBeforeUnload)
})

const newLessonResource = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Course Lesson',
				course: props.courseName,
				chapter: lessonDetails.data?.chapter.name,
				...values.lessonData,
			},
		}
	},
})

const editLesson = createResource({
	url: 'frappe.client.set_value',
	makeParams(values) {
		return {
			doctype: 'Course Lesson',
			name: values.lessonName,
			fieldname: values.lessonData,
		}
	},
})

const lessonReference = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Lesson Reference',
				parent: lessonDetails.data?.chapter.name,
				parenttype: 'Course Chapter',
				parentfield: 'lessons',
				lesson: values.lesson,
				idx: props.lessonNumber,
			},
		}
	},
})

const convertToJSON = (lessonData) => {
	let blocks = []
	if (lessonData.youtube) {
		let youtubeID = lessonData.youtube.split('/').pop()
		blocks.push({
			type: 'embed',
			data: {
				service: 'youtube',
				embed: `https://www.youtube.com/embed/${youtubeID}`,
			},
		})
	}
	lessonData.body.split('\n').forEach((block) => {
		if (block.includes('{{ YouTubeVideo')) {
			let youtubeID = block.match(/\(["']([^"']+?)["']\)/)[1]
			if (!youtubeID.includes('https://'))
				youtubeID = `https://www.youtube.com/embed/${youtubeID}`
			blocks.push({
				type: 'embed',
				data: {
					service: 'youtube',
					embed: youtubeID,
				},
			})
		} else if (block.includes('{{ Quiz')) {
			let quiz = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'quiz',
				data: {
					quiz: quiz,
				},
			})
		} else if (block.includes('{{ Video')) {
			let video = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: video,
					file_type: video.split('.').pop(),
				},
			})
		} else if (block.includes('{{ Audio')) {
			let audio = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: audio,
					file_type: audio.split('.').pop(),
				},
			})
		} else if (block.includes('{{ PDF')) {
			let pdf = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: pdf,
					file_type: 'pdf',
				},
			})
		} else if (block.includes('{{ Embed')) {
			let embed = block.match(/\(["']([^"']+?)["']\)/)[1]
			let embedParts = embed.split('|||')
			let embedUrl = embedParts.length > 1 ? embedParts[1] : embed
			blocks.push({
				type: 'embed',
				data: {
					service:
						embedParts.length > 1 ? embedParts[0] : getEmbedService(embedUrl),
					embed: embedUrl,
				},
			})
		} else if (block.includes('![]')) {
			let image = block.match(/\((.*?)\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: image,
					file_type: 'image',
				},
			})
		} else if (block.includes('#')) {
			let level = (block.match(/#/g) || []).length
			blocks.push({
				type: 'header',
				data: {
					text: block.replace(/#/g, '').trim(),
					level: level,
				},
			})
		} else {
			blocks.push({
				type: 'paragraph',
				data: {
					text: block,
				},
			})
		}
	})

	if (lessonData.quizId) {
		blocks.push({
			type: 'quiz',
			data: {
				quiz: lessonData.quizId,
			},
		})
	}
	if (lessonData.quiz_id) {
		blocks.push({
			type: 'quiz',
			data: {
				quiz: lessonData.quiz_id,
			},
		})
	}

	return blocks
}

const isImportedHtmlLesson = (lessonData) => {
	if (!lessonData?.body || lessonData.content) return false
	return /<\/?(div|p|span|img|video|source|iframe|table|thead|tbody|tr|td|th|h[1-6]|ul|ol|li|a)\b/i.test(
		lessonData.body
	)
}

const getEmbedService = (url) => {
	if (url.includes('youtube.com') || url.includes('youtu.be')) return 'youtube'
	if (/https?:\/\/(?:[^/]+\.)?h5p\.com(?:\/|$)/i.test(url)) return 'h5p'
	if (url.includes('docs.google.com/presentation')) return 'googleSlides'
	if (url.includes('mentimeter.com')) return 'mentimeter'
	if (url.includes('menti.com')) return 'menti'
	return 'genericEmbed'
}

const getHtmlCheckIssues = () => {
	let body = lesson.body || ''
	let issues = []

	if (body.includes('$IMS-CC-FILEBASE$')) {
		issues.push(
			__(
				'There are unresolved Canvas file links. Re-import or replace them with Frappe file URLs.'
			)
		)
	}
	if (/data-api-(endpoint|returntype)=/i.test(body)) {
		issues.push(__('Canvas API attributes are still present in the HTML.'))
	}
	if (/<video\b(?![^>]*\bcontrols\b)[^>]*>/i.test(body)) {
		issues.push(__('At least one video tag is missing controls.'))
	}
	if (/<(?:img|iframe|source)\b[^>]*\bsrc=(["'])\s*\1/i.test(body)) {
		issues.push(__('At least one media element has an empty source.'))
	}
	if (/<script\b/i.test(body)) {
		issues.push(__('Script tags should not be used inside lessons.'))
	}
	if (/\b(?:src|href)=(["'])http:\/\//i.test(body)) {
		issues.push(
			__(
				'At least one embedded resource uses HTTP and may be blocked when the LMS uses HTTPS.'
			)
		)
	}

	return issues
}

const checkHtmlLesson = () => {
	htmlCheckIssues.value = getHtmlCheckIssues()
	htmlCheckRan.value = true
	if (!htmlCheckIssues.value.length) {
		toast.success(__('No obvious HTML issues found'))
	}
}

const saveLesson = async ({ showSuccessMessage = false } = {}) => {
	if (isSaving.value) return
	isSaving.value = true

	try {
		const lessonData = await buildLessonData()
		const validationError = validateLesson(lessonData)
		if (validationError) {
			toast.error(validationError)
			return
		}

		if (lessonDetails.data?.lesson) {
			await editCurrentLesson(lessonData, showSuccessMessage)
		} else {
			await createNewLesson(lessonData)
		}
	} catch (error) {
		toast.error(
			error?.messages?.[0] ||
				error?.message ||
				__('Unable to save the lesson. Please try again.')
		)
	} finally {
		isSaving.value = false
	}
}

const buildLessonData = async () => {
	let instructorOutput = await instructorEditor.value.save()
	instructorOutput = removeEmptyBlocks(instructorOutput)

	const lessonData = {
		...lesson,
		instructor_content: JSON.stringify(instructorOutput),
	}

	if (htmlBodyMode.value) {
		lessonData.content = ''
		htmlCheckIssues.value = getHtmlCheckIssues()
		htmlCheckRan.value = htmlCheckIssues.value.length > 0
		return lessonData
	}

	let outputData = await editor.value.save()
	outputData = removeEmptyBlocks(outputData)
	lessonData.content = JSON.stringify(outputData)
	lessonData.body = ''
	return lessonData
}

const removeEmptyBlocks = (outputData) => {
	let blocks = outputData.blocks.filter((block) => {
		return Object.keys(block.data).length > 0 || block.type == 'paragraph'
	})
	outputData.blocks = blocks
	return outputData
}

const createNewLesson = async (lessonData) => {
	const data = await newLessonResource.submit({ lessonData }, { onError() {} })
	await lessonReference.submit({ lesson: data.name }, { onError() {} })

	if (user.data?.is_system_manager) updateOnboardingStep('create_first_lesson')

	capture('lesson_created')
	isDirty.value = false
	toast.success(__('Lesson created successfully'))
	await lessonDetails.reload()
}

const editCurrentLesson = async (lessonData, showSuccessMessage) => {
	await editLesson.submit(
		{
			lessonName: lessonDetails.data.lesson.name,
			lessonData,
		},
		{ onError() {} }
	)

	isHydrating.value = true
	Object.assign(lesson, lessonData)
	await nextTick()
	isDirty.value = false
	isHydrating.value = false
	if (showSuccessMessage) {
		toast.success(__('Lesson updated successfully'))
	}
}

const validateLesson = (lessonData) => {
	if (!lessonData.title) {
		return __('Title is required')
	}
	if (htmlBodyMode.value && !lessonData.body?.trim()) {
		return __('Content is required')
	}
	if (htmlBodyMode.value && /<script\b/i.test(lessonData.body || '')) {
		return __('Script tags should not be used inside lessons.')
	}
	if (
		htmlBodyMode.value &&
		(lessonData.body || '').includes('$IMS-CC-FILEBASE$')
	) {
		return __('Resolve Canvas file links before saving.')
	}
	if (!htmlBodyMode.value && !lessonData.content) {
		return __('Content is required')
	}
}

const breadcrumbs = computed(() => {
	let crumbs = [
		{
			label: __('Courses'),
			route: { name: 'Courses' },
		},
		{
			label: lessonDetails.data?.course_title,
			route: {
				name: 'CourseDetail',
				params: { courseName: props.courseName },
				hash: '#settings',
			},
		},
	]

	if (lessonDetails?.data?.lesson) {
		crumbs.push({
			label: lessonDetails.data.lesson.title,
			route: {
				name: 'Lesson',
				params: {
					courseName: props.courseName,
					chapterNumber: props.chapterNumber,
					lessonNumber: props.lessonNumber,
				},
			},
		})
	}
	crumbs.push({
		label: lessonDetails?.data?.lesson
			? __('Edit Lesson')
			: __('Create Lesson'),
		route: {
			name: 'LessonForm',
			params: {
				courseName: props.courseName,
				chapterNumber: props.chapterNumber,
				lessonNumber: props.lessonNumber,
			},
		},
	})
	return crumbs
})

usePageMeta(() => {
	return {
		title: lessonDetails?.data?.lesson
			? lessonDetails.data.lesson.title
			: __('New Lesson'),
		icon: brand.favicon,
	}
})
</script>
<style>
.embed-tool__caption,
.cdx-simple-image__caption {
	display: none;
}

.ce-block__content {
	max-width: none;
}

.ce-toolbar__actions,
.codex-editor--narrow .ce-toolbar__actions {
	right: auto;
	left: auto;
	inset-inline-end: 100%;
}

.codex-editor--narrow .codex-editor__redactor {
	margin-inline: 0;
}

.ce-toolbar__content {
	max-width: none;
}

.codeBoxHolder {
	display: flex;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
}

.codeBoxTextArea {
	width: 100%;
	min-height: 30px;
	padding: 10px;
	border-radius: 2px 2px 2px 0;
	border: none !important;
	outline: none !important;
	font: 14px monospace;
}

.codeBoxSelectDiv {
	display: flex;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
	position: relative;
}

.codeBoxSelectInput {
	border-radius: 0 0 20px 2px;
	padding: 2px 26px;
	padding-top: 0;
	padding-inline-end: 0;
	text-align: start;
	cursor: pointer;
	border: none !important;
	outline: none !important;
}

.codeBoxSelectDropIcon {
	position: absolute !important;
	inset-inline-start: 10px !important;
	bottom: 0 !important;
	width: unset !important;
	height: unset !important;
	font-size: 16px !important;
}

.codeBoxSelectPreview {
	display: none;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
	border-radius: 2px;
	box-shadow: 0 3px 15px -3px rgba(13, 20, 33, 0.13);
	position: absolute;
	top: 100%;
	margin: 5px 0;
	max-height: 30vh;
	overflow-x: hidden;
	overflow-y: auto;
	z-index: 10000;
}

.codeBoxSelectItem {
	width: 100%;
	padding: 5px 20px;
	margin: 0;
	cursor: pointer;
}

.codeBoxSelectedItem {
	background-color: lightblue !important;
}

.codeBoxShow {
	display: flex !important;
}

.dark {
	color: #abb2bf;
	background-color: #282c34;
}

.light {
	color: #383a42;
	background-color: #fafafa;
}

.codeBoxTextArea {
	line-height: 1.7;
}

.prose :where(pre):not(:where([class~='not-prose'], [class~='not-prose'] *)) {
	overflow-x: unset;
}

iframe {
	border: none !important;
}

.tc-table {
	border-inline-start: 1px solid #e8e8eb;
}

.ce-toolbox__button[data-tool='markdown'] {
	display: none !important;
}

.ce-popover-item[data-item-name='markdown'] {
	display: none !important;
}

.plyr__volume input[type='range'] {
	display: none;
}

.plyr__control--overlaid {
	background: radial-gradient(
		circle,
		rgba(0, 0, 0, 0.4) 0%,
		rgba(0, 0, 0, 0.5) 50%
	);
}

.plyr__control:hover {
	background: none;
}

.plyr--video {
	border: 1px solid theme('colors.gray.200');
	border-radius: 8px;
}

.ce-popover__container {
	border-radius: 12px;
	padding: 8px;
}

.ce-popover,
.codex-editor--narrow .ce-toolbox .ce-popover,
.codex-editor--narrow .ce-toolbar__actions .ce-popover {
	border-radius: 12px;
	right: auto;
	left: auto;
	inset-inline-start: 0;
}

.cdx-search-field {
	border: none;
}

.cdx-search-field__input {
	font-weight: 400;
	font-size: 13px;
}

.cdx-search-field__input::before {
	font-weight: 400;
}

.cdx-search-field__input:focus {
	--tw-ring-color: theme('colors.gray.100');
}

.ce-popover-item__title {
	font-size: 13px;
	font-weight: 400;
}

.ce-popover-item__icon svg {
	width: 15px;
	height: 15px;
}

.ce-popover-item__icon {
	margin-right: unset;
	margin-inline-end: 10px;
}

.ce-popover--opened {
	max-height: unset !important;
}

.cdx-search-field__icon svg {
	width: 15px;
	height: 15px;
}

.cdx-search-field__icon {
	margin-inline-end: 5px;
}

.cdx-block.embed-tool {
	position: relative;
	display: inline-block;
	width: 100%;
}

:root {
	--plyr-range-fill-background: white;
	--plyr-video-control-background-hover: transparent;
}
</style>
