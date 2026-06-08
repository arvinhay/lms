import zipfile
from io import BytesIO
from unittest import TestCase

from lms.lms.imscc_import import (
	_build_external_resource_body,
	_clean_html,
	_get_modules,
	_get_modules_from_manifest,
)


class TestIMSCCImport(TestCase):
	def test_clean_html_preserves_embeds_and_resolves_relative_assets(self):
		raw_html = """
			<html><body>
				<img src="../web_resources/Uploaded%20Media/Test.png"
					data-api-endpoint="https://canvas.example/api/file">
				<iframe src="https://tenant.h5p.com/content/123/embed" loading="lazy"></iframe>
			</body></html>
		"""

		body = _clean_html(
			raw_html,
			{"web_resources/Uploaded Media/Test.png": "/files/Test.png"},
			"wiki_content/page.html",
		)

		self.assertIn('src="/files/Test.png"', body)
		self.assertIn('src="https://tenant.h5p.com/content/123/embed"', body)
		self.assertIn('loading="lazy"', body)
		self.assertNotIn("data-api-endpoint", body)

	def test_manifest_hierarchy_becomes_chapters_with_ordered_lessons(self):
		manifest = """
			<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1">
				<organizations>
					<organization>
						<item>
							<title>Module One</title>
							<item identifierref="page-one"><title>First page</title></item>
							<item identifierref="page-two"><title>Second page</title></item>
						</item>
						<item>
							<title>Module Two</title>
							<item identifierref="page-three"><title>Third page</title></item>
						</item>
					</organization>
				</organizations>
			</manifest>
		"""
		buffer = BytesIO()
		with zipfile.ZipFile(buffer, "w") as archive:
			archive.writestr("imsmanifest.xml", manifest)

		buffer.seek(0)
		with zipfile.ZipFile(buffer) as archive:
			modules = _get_modules_from_manifest(
				archive,
				{
					"page-one": {"type": "webcontent"},
					"page-two": {"type": "webcontent"},
					"page-three": {"type": "webcontent"},
				},
			)

		self.assertEqual([module["title"] for module in modules], ["Module One", "Module Two"])
		self.assertEqual(
			[item["identifierref"] for item in modules[0]["items"]],
			["page-one", "page-two"],
		)

	def test_external_learning_tools_keep_their_embed(self):
		body = _build_external_resource_body(
			"https://example.h5p.com/content/123/embed",
			"Interactive activity",
		)

		self.assertIn("<iframe", body)
		self.assertIn("https://example.h5p.com/content/123/embed", body)
		self.assertIn("allowfullscreen", body)

	def test_canvas_front_page_is_prepended_when_module_meta_omits_it(self):
		manifest = """
			<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1">
				<resources>
					<resource identifier="front-page" type="webcontent" href="wiki_content/home.html">
						<file href="wiki_content/home.html" />
					</resource>
					<resource identifier="module-page" type="webcontent" href="wiki_content/lesson.html">
						<file href="wiki_content/lesson.html" />
					</resource>
				</resources>
			</manifest>
		"""
		module_meta = """
			<modules>
				<module>
					<title>Module 1</title>
					<position>1</position>
					<items>
						<item>
							<title>Lesson 1</title>
							<identifierref>module-page</identifierref>
							<content_type>WikiPage</content_type>
							<position>1</position>
						</item>
					</items>
				</module>
			</modules>
		"""
		front_page = """
			<html>
				<head>
						<title>Course Front Page</title>
						<meta content="true" name="front_page">
				</head>
				<body>
					<video><source src="$IMS-CC-FILEBASE$/intro.mp4"></video>
				</body>
			</html>
		"""
		buffer = BytesIO()
		with zipfile.ZipFile(buffer, "w") as archive:
			archive.writestr("imsmanifest.xml", manifest)
			archive.writestr("course_settings/module_meta.xml", module_meta)
			archive.writestr("wiki_content/home.html", front_page)
			archive.writestr("wiki_content/lesson.html", "<html><body>Lesson</body></html>")

		buffer.seek(0)
		with zipfile.ZipFile(buffer) as archive:
			modules = _get_modules(
				archive,
				{
					"front-page": {
						"href": "wiki_content/home.html",
						"type": "webcontent",
						"files": ["wiki_content/home.html"],
						"dependencies": [],
					},
					"module-page": {
						"href": "wiki_content/lesson.html",
						"type": "webcontent",
						"files": ["wiki_content/lesson.html"],
						"dependencies": [],
					},
				},
			)

		self.assertEqual(modules[0]["items"][0]["identifierref"], "front-page")
		self.assertEqual(modules[0]["items"][0]["title"], "Course Front Page")
		self.assertEqual(modules[0]["items"][1]["identifierref"], "module-page")
