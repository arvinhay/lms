import zipfile
from io import BytesIO
from unittest import TestCase

from lms.lms.imscc_import import (
	_build_external_resource_body,
	_clean_html,
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
