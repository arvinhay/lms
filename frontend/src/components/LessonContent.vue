<template>
	<div v-if="youtube">
		<iframe
			class="youtube-video lms-responsive-media lms-aspect-video"
			:src="getYouTubeVideoSource(youtube.split('/').pop())"
			width="100%"
			:height="screenSize.width < 640 ? 200 : 400"
			frameborder="0"
			allowfullscreen
		></iframe>
	</div>
	<div
		v-if="!hasEmbeddedBlocks"
		:class="{ 'lms-html-document': hasHtmlDocument(content) }"
		v-html="renderDocument(content)"
	></div>
	<template v-else>
		<div v-for="block in content?.split('\n\n')">
			<div v-if="block.includes('{{ YouTubeVideo')">
				<iframe
					class="youtube-video lms-responsive-media lms-aspect-video"
					:src="getYouTubeVideoSource(block)"
					width="100%"
					:height="screenSize.width < 640 ? 200 : 400"
					frameborder="0"
					allowfullscreen
				></iframe>
			</div>
			<div v-else-if="block.includes('{{ Quiz') && !quizId">
				<Quiz :quiz="getId(block)" />
			</div>
			<div v-else-if="block.includes('{{ Video')">
				<video
					class="lms-responsive-media"
					controls
					width="100%"
					controlsList="nodownload"
					oncontextmenu="return false"
				>
					<source :src="getId(block)" type="video/mp4" />
				</video>
			</div>
			<div v-else-if="block.includes('{{ PDF')">
				<iframe
					class="lms-responsive-media lms-document-frame"
					:src="getPDFSource(block)"
					width="100%"
					height="700px"
					frameborder="0"
					allowfullscreen
				></iframe>
			</div>
			<div v-else-if="block.includes('{{ Audio')">
				<audio width="100%" controls controlsList="nodownload">
					<source :src="getId(block)" type="audio/mp3" />
				</audio>
			</div>
			<div v-else-if="block.includes('{{ Embed')">
				<iframe
					:class="['lms-responsive-media', getEmbedClass(block)]"
					width="100%"
					:height="getEmbedHeight(block)"
					:src="getId(block)"
					frameborder="0"
					allow="
						autoplay *;
						geolocation *;
						microphone *;
						camera *;
						midi *;
						encrypted-media *;
					"
					allowfullscreen
				>
				</iframe>
			</div>
			<div
				v-else
				:class="{ 'lms-html-document': hasHtmlDocument(block) }"
				v-html="renderSafe(block)"
			></div>
		</div>
	</template>
	<div v-if="quizId">
		<Quiz :quiz="quizId" />
	</div>
</template>
<script setup>
import Quiz from '@/components/QuizBlock.vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { useScreenSize } from '@/utils/composables'
import { computed, onMounted, watch } from 'vue'

const screenSize = useScreenSize()

const markdown = new MarkdownIt({
	html: true,
	linkify: true,
})

const sanitizerOptions = {
	ADD_TAGS: ['iframe'],
	ADD_ATTR: [
		'allow',
		'allowfullscreen',
		'frameborder',
		'loading',
		'mozallowfullscreen',
		'webkitallowfullscreen',
	],
}

const renderSafe = (block) =>
	DOMPurify.sanitize(markdown.render(block), sanitizerOptions)

const hasHtmlDocument = (value) => /<\/?[a-z][\s\S]*>/i.test(value || '')

const renderDocument = (value) => {
	const source = hasHtmlDocument(value) ? value : markdown.render(value || '')
	return DOMPurify.sanitize(source, sanitizerOptions)
}

const props = defineProps({
	content: {
		type: String,
		required: true,
	},
	youtube: {
		type: String,
		required: false,
	},
	quizId: {
		type: String,
		required: false,
	},
})

const getYouTubeVideoSource = (block) => {
	if (block.includes('{{')) {
		block = getId(block)
	}
	return `https://www.youtube.com/embed/${block}`
}

const getPDFSource = (block) => {
	return `${getId(block)}#toolbar=0`
}

const getId = (block) => {
	return block.match(/\(["']([^"']+?)["']\)/)[1]
}

const hasEmbeddedBlocks = computed(() =>
	/{{\s*(YouTubeVideo|Quiz|Video|PDF|Audio|Embed)\s*\(/.test(
		props.content || '',
	),
)

const h5pResizerUrls = computed(() => {
	const resizerUrls = new Set()
	const iframePattern = /<iframe\b[^>]*\bsrc=(["'])(.*?)\1/gi
	let match

	while ((match = iframePattern.exec(props.content || ''))) {
		try {
			const source = new URL(match[2], window.location.origin)
			if (
				source.hostname === 'h5p.com' ||
				source.hostname.endsWith('.h5p.com')
			) {
				resizerUrls.add(`${source.origin}/js/h5p-resizer.js`)
			}
		} catch {
			// Invalid iframe URLs are reported by the HTML lesson checker.
		}
	}

	return Array.from(resizerUrls)
})

const loadH5PResizer = () => {
	h5pResizerUrls.value.forEach((url) => {
		const scriptId = `h5p-resizer-${new URL(url).hostname.replaceAll('.', '-')}`
		if (document.getElementById(scriptId)) return

		const script = document.createElement('script')
		script.id = scriptId
		script.src = url
		script.async = true
		document.body.appendChild(script)
	})
}

const getEmbedHeight = (block) => {
	const src = getId(block).toLowerCase()
	if (screenSize.width < 640) {
		if (src.includes('youtube.com') || src.includes('youtu.be')) return 220
		if (src.includes('vimeo.com')) return 220
		if (src.includes('docs.google.com/presentation')) return 320
		return 620
	}

	if (src.includes('youtube.com') || src.includes('youtu.be')) return 480
	if (src.includes('vimeo.com')) return 480
	if (src.includes('docs.google.com/presentation')) return 620
	if (src.includes('mentimeter.com') || src.includes('menti.com')) return 720
	if (src.includes('h5p.com')) return 900
	return 640
}

const getEmbedClass = (block) => {
	const src = getId(block).toLowerCase()
	if (
		src.includes('youtube.com') ||
		src.includes('youtu.be') ||
		src.includes('vimeo.com') ||
		src.includes('docs.google.com/presentation')
	) {
		return 'lms-aspect-video'
	}
	if (src.includes('h5p.com')) return 'lms-h5p-frame'
	return ''
}

onMounted(loadH5PResizer)
watch(() => props.content, loadH5PResizer)
</script>
