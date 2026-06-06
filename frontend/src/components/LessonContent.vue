<template>
	<div v-if="youtube">
		<iframe
			class="youtube-video"
			:src="getYouTubeVideoSource(youtube.split('/').pop())"
			width="100%"
			:height="screenSize.width < 640 ? 200 : 400"
			frameborder="0"
			allowfullscreen
		></iframe>
	</div>
	<div v-if="!hasEmbeddedBlocks" v-html="renderDocument(content)"></div>
	<template v-else>
		<div v-for="block in content?.split('\n\n')">
			<div v-if="block.includes('{{ YouTubeVideo')">
				<iframe
					class="youtube-video"
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
					controls
					width="100%"
					controlsList="nodownload"
					oncontextmenu="return false;"
				>
					<source :src="getId(block)" type="video/mp4" />
				</video>
			</div>
			<div v-else-if="block.includes('{{ PDF')">
				<iframe
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
					width="100%"
					:height="getEmbedHeight(block)"
					:src="getId(block)"
					frameborder="0"
					allow="autoplay *; geolocation *; microphone *; camera *; midi *; encrypted-media *"
					allowfullscreen
				>
				</iframe>
			</div>
			<div v-else v-html="renderSafe(block)"></div>
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

const renderSafe = (block) => DOMPurify.sanitize(markdown.render(block))

const renderDocument = (value) => {
	const source = /<\/?[a-z][\s\S]*>/i.test(value || '')
		? value
		: markdown.render(value || '')
	return DOMPurify.sanitize(source)
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

const hasH5PEmbed = computed(() =>
	props.content?.includes('refugee-education.h5p.com')
)

const hasEmbeddedBlocks = computed(() =>
	/{{\s*(YouTubeVideo|Quiz|Video|PDF|Audio|Embed)\s*\(/.test(
		props.content || ''
	)
)

const loadH5PResizer = () => {
	if (!hasH5PEmbed.value || document.getElementById('h5p-resizer-script')) return

	const script = document.createElement('script')
	script.id = 'h5p-resizer-script'
	script.src = 'https://refugee-education.h5p.com/js/h5p-resizer.js'
	script.async = true
	document.body.appendChild(script)
}

const getEmbedHeight = (block) => {
	const src = getId(block)
	if (screenSize.width < 640) {
		if (src.includes('youtube.com')) return 220
		if (src.includes('docs.google.com/presentation')) return 320
		return 620
	}

	if (src.includes('youtube.com')) return 480
	if (src.includes('docs.google.com/presentation')) return 620
	if (src.includes('mentimeter.com') || src.includes('menti.com')) return 720
	if (src.includes('h5p.com')) return 900
	return 640
}

onMounted(loadH5PResizer)
watch(hasH5PEmbed, loadH5PResizer)
</script>
