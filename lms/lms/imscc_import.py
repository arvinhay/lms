"""Canvas IMSCC import helpers for Frappe LMS."""

from __future__ import annotations

import html
import os
import re
import zipfile
from urllib.parse import quote, unquote
import xml.etree.ElementTree as ET

import frappe
from frappe import _
from frappe.utils.file_manager import is_safe_path

from lms.lms.utils import get_lesson_count


WEB_RESOURCE_PREFIX = "web_resources/"
IMSCC_FILEBASE = "$IMS-CC-FILEBASE$/"
DEFAULT_PASSING_PERCENTAGE = 50


def import_course_from_imscc(imscc_file_path: str) -> str:
	"""Import a Canvas Common Cartridge into native Frappe LMS records."""

	actual_path = _get_actual_file_path(imscc_file_path)
	_validate_imscc_file(actual_path)

	with zipfile.ZipFile(actual_path, "r") as zip_file:
		resources = _get_manifest_resources(zip_file)
		asset_map = _create_assets(zip_file)
		course = _create_course(zip_file, resources, asset_map)
		modules = _get_modules(zip_file, resources)

		for chapter_idx, module in enumerate(modules, start=1):
			chapter = _create_chapter(course.name, module["title"])
			_create_chapter_reference(course.name, chapter.name, chapter_idx)

			for lesson_idx, item in enumerate(module.get("items", []), start=1):
				lesson = _create_lesson_from_item(
					zip_file=zip_file,
					course_name=course.name,
					chapter_name=chapter.name,
					item=item,
					resources=resources,
					asset_map=asset_map,
				)
				if lesson:
					_create_lesson_reference(chapter.name, lesson.name, lesson_idx)

		frappe.db.set_value("LMS Course", course.name, "lessons", get_lesson_count(course.name))
		return course.name


def _get_actual_file_path(file_path: str) -> str:
	if not file_path:
		frappe.throw(_("Missing IMSCC file"))

	file_path = file_path.lstrip("/")
	return frappe.get_site_path(file_path)


def _validate_imscc_file(file_path: str) -> None:
	if not os.path.exists(file_path) or not zipfile.is_zipfile(file_path):
		frappe.throw(_("Invalid IMSCC file"))

	if not is_safe_path(file_path):
		frappe.throw(_("Unsafe file path detected"))


def _read_xml(zip_file: zipfile.ZipFile, path: str):
	if path not in zip_file.namelist():
		return None

	try:
		return ET.fromstring(zip_file.read(path))
	except ET.ParseError:
		frappe.log_error(frappe.get_traceback(), f"Could not parse IMSCC XML file: {path}")
		return None


def _read_text(zip_file: zipfile.ZipFile, path: str) -> str:
	if path not in zip_file.namelist():
		return ""

	return zip_file.read(path).decode("utf-8", errors="replace")


def _local_name(tag: str) -> str:
	return tag.rsplit("}", 1)[-1]


def _children(element, name: str | None = None):
	if element is None:
		return []

	return [child for child in list(element) if name is None or _local_name(child.tag) == name]


def _first_child(element, name: str):
	matches = _children(element, name)
	return matches[0] if matches else None


def _descendants(element, name: str):
	if element is None:
		return []

	return [child for child in element.iter() if _local_name(child.tag) == name]


def _text(element, name: str | None = None, default: str = "") -> str:
	target = _first_child(element, name) if name else element
	if target is None or target.text is None:
		return default

	return target.text.strip()


def _get_manifest_resources(zip_file: zipfile.ZipFile) -> dict:
	root = _read_xml(zip_file, "imsmanifest.xml")
	resources = {}

	for resource in _descendants(root, "resource"):
		identifier = resource.attrib.get("identifier")
		if not identifier:
			continue

		resources[identifier] = {
			"href": resource.attrib.get("href"),
			"type": resource.attrib.get("type"),
			"files": [
				file_node.attrib.get("href")
				for file_node in _children(resource, "file")
				if file_node.attrib.get("href")
			],
			"dependencies": [
				dependency.attrib.get("identifierref")
				for dependency in _children(resource, "dependency")
				if dependency.attrib.get("identifierref")
			],
		}

	return resources


def _create_assets(zip_file: zipfile.ZipFile) -> dict:
	asset_map = {}

	for path in zip_file.namelist():
		if not path.startswith(WEB_RESOURCE_PREFIX) or path.endswith("/"):
			continue

		try:
			file_doc = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": os.path.basename(path),
					"is_private": 0,
					"content": zip_file.read(path),
				}
			).insert(ignore_permissions=True)
			asset_map[path] = file_doc.file_url
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Could not import IMSCC asset: {path}")

	return asset_map


def _create_course(zip_file: zipfile.ZipFile, resources: dict, asset_map: dict):
	title = _get_course_title(zip_file)
	image = _get_course_image(zip_file, resources, asset_map)

	return frappe.get_doc(
		{
			"doctype": "LMS Course",
			"title": title,
			"short_introduction": _("Imported from Canvas IMSCC."),
			"description": _("Imported from Canvas IMSCC. Review and publish when ready."),
			"image": image,
			"published": 0,
			"instructors": [{"instructor": frappe.session.user}],
		}
	).insert(ignore_permissions=True)


def _get_course_title(zip_file: zipfile.ZipFile) -> str:
	course_settings = _read_xml(zip_file, "course_settings/course_settings.xml")
	title = _text(course_settings, "title")
	if title:
		return title

	manifest = _read_xml(zip_file, "imsmanifest.xml")
	for title_node in _descendants(manifest, "title"):
		string_node = _first_child(title_node, "string")
		if string_node is not None and _text(string_node):
			return _text(string_node)

	return _("Imported Canvas Course")


def _get_course_image(zip_file: zipfile.ZipFile, resources: dict, asset_map: dict) -> str | None:
	course_settings = _read_xml(zip_file, "course_settings/course_settings.xml")
	image_identifier = _text(course_settings, "image_identifier_ref")
	if not image_identifier:
		return None

	resource = resources.get(image_identifier, {})
	image_path = resource.get("href") or next(iter(resource.get("files", [])), None)
	return asset_map.get(image_path)


def _get_modules(zip_file: zipfile.ZipFile, resources: dict) -> list[dict]:
	modules = _get_modules_from_canvas_meta(zip_file)
	if modules:
		return modules

	modules = _get_modules_from_manifest(zip_file, resources)
	if modules:
		return modules

	return _get_modules_from_wiki_resources(resources)


def _get_modules_from_canvas_meta(zip_file: zipfile.ZipFile) -> list[dict]:
	root = _read_xml(zip_file, "course_settings/module_meta.xml")
	modules = []

	for module in _children(root, "module"):
		items = []
		items_node = _first_child(module, "items")
		for item in _children(items_node, "item"):
			items.append(
				{
					"title": _text(item, "title"),
					"identifierref": _text(item, "identifierref"),
					"content_type": _text(item, "content_type"),
					"position": _safe_int(_text(item, "position"), len(items) + 1),
				}
			)

		if items:
			modules.append(
				{
					"title": _text(module, "title") or _("Untitled Module"),
					"position": _safe_int(_text(module, "position"), len(modules) + 1),
					"items": sorted(items, key=lambda row: row["position"]),
				}
			)

	return sorted(modules, key=lambda row: row["position"])


def _get_modules_from_manifest(zip_file: zipfile.ZipFile, resources: dict) -> list[dict]:
	root = _read_xml(zip_file, "imsmanifest.xml")
	organization = next(iter(_descendants(root, "organization")), None)
	items = []

	for item in _descendants(organization, "item"):
		identifierref = item.attrib.get("identifierref")
		if not identifierref:
			continue

		items.append(
			{
				"title": _text(item, "title") or _title_from_resource(resources, identifierref),
				"identifierref": identifierref,
				"content_type": _content_type_from_resource(resources, identifierref),
				"position": len(items) + 1,
			}
		)

	if not items:
		return []

	return [{"title": _("Course Content"), "position": 1, "items": items}]


def _get_modules_from_wiki_resources(resources: dict) -> list[dict]:
	items = []
	for identifier, resource in resources.items():
		href = resource.get("href")
		if resource.get("type") == "webcontent" and href and href.startswith("wiki_content/"):
			items.append(
				{
					"title": _title_from_href(href),
					"identifierref": identifier,
					"content_type": "WikiPage",
					"position": len(items) + 1,
				}
			)

	if not items:
		frappe.throw(_("No importable lessons were found in this IMSCC file."))

	return [{"title": _("Course Content"), "position": 1, "items": items}]


def _create_chapter(course_name: str, title: str):
	return frappe.get_doc(
		{
			"doctype": "Course Chapter",
			"course": course_name,
			"title": title or _("Untitled Module"),
		}
	).insert(ignore_permissions=True)


def _create_chapter_reference(course_name: str, chapter_name: str, idx: int) -> None:
	frappe.get_doc(
		{
			"doctype": "Chapter Reference",
			"parent": course_name,
			"parenttype": "LMS Course",
			"parentfield": "chapters",
			"idx": idx,
			"chapter": chapter_name,
		}
	).insert(ignore_permissions=True)


def _create_lesson_reference(chapter_name: str, lesson_name: str, idx: int) -> None:
	frappe.get_doc(
		{
			"doctype": "Lesson Reference",
			"parent": chapter_name,
			"parenttype": "Course Chapter",
			"parentfield": "lessons",
			"idx": idx,
			"lesson": lesson_name,
		}
	).insert(ignore_permissions=True)


def _create_lesson_from_item(
	zip_file: zipfile.ZipFile,
	course_name: str,
	chapter_name: str,
	item: dict,
	resources: dict,
	asset_map: dict,
):
	content_type = item.get("content_type") or _content_type_from_resource(resources, item.get("identifierref"))
	if _is_quiz_item(content_type, resources.get(item.get("identifierref"), {})):
		return _create_quiz_lesson(zip_file, course_name, chapter_name, item, resources, asset_map)

	return _create_html_lesson(zip_file, course_name, chapter_name, item, resources, asset_map)


def _create_html_lesson(
	zip_file: zipfile.ZipFile,
	course_name: str,
	chapter_name: str,
	item: dict,
	resources: dict,
	asset_map: dict,
):
	resource = resources.get(item.get("identifierref"), {})
	href = resource.get("href") or next(iter(resource.get("files", [])), None)
	if not href:
		return None

	body = _clean_html(_read_text(zip_file, href), asset_map)
	title = item.get("title") or _extract_html_title(body) or _title_from_href(href)

	return frappe.get_doc(
		{
			"doctype": "Course Lesson",
			"chapter": chapter_name,
			"course": course_name,
			"title": title,
			"body": body,
			"content": None,
		}
	).insert(ignore_permissions=True)


def _create_quiz_lesson(
	zip_file: zipfile.ZipFile,
	course_name: str,
	chapter_name: str,
	item: dict,
	resources: dict,
	asset_map: dict,
):
	quiz = _create_quiz(zip_file, course_name, item, resources, asset_map)
	if not quiz:
		return None

	lesson = frappe.get_doc(
		{
			"doctype": "Course Lesson",
			"chapter": chapter_name,
			"course": course_name,
			"title": item.get("title") or quiz.title,
			"body": "",
			"quiz_id": quiz.name,
			"content": None,
		}
	).insert(ignore_permissions=True)
	frappe.db.set_value("LMS Quiz", quiz.name, "lesson", lesson.name, update_modified=False)
	return lesson


def _create_quiz(
	zip_file: zipfile.ZipFile,
	course_name: str,
	item: dict,
	resources: dict,
	asset_map: dict,
):
	identifier = item.get("identifierref")
	qti_path = _get_qti_path(zip_file, identifier, resources)
	if not qti_path:
		return None

	qti_root = _read_xml(zip_file, qti_path)
	assessment = next(iter(_descendants(qti_root, "assessment")), None)
	title = item.get("title") or assessment.attrib.get("title") if assessment is not None else item.get("title")
	question_rows = []

	for item_node in _descendants(qti_root, "item"):
		question = _create_question(item_node, asset_map)
		if question:
			question_rows.append(
				{
					"question": question.name,
					"marks": _get_question_marks(item_node),
					"type": question.type,
				}
			)

	return frappe.get_doc(
		{
			"doctype": "LMS Quiz",
			"title": title or _("Imported Quiz"),
			"course": course_name,
			"questions": question_rows,
			"passing_percentage": _get_passing_percentage(zip_file, identifier),
			"show_answers": 1,
		}
	).insert(ignore_permissions=True)


def _create_question(item_node, asset_map: dict):
	question_type = _get_qti_metadata(item_node, "question_type")
	question_html = _replace_asset_refs(_get_question_text(item_node), asset_map)

	if question_type in ("essay_question", "file_upload_question"):
		return frappe.get_doc(
			{
				"doctype": "LMS Question",
				"question": question_html,
				"type": "Open Ended",
			}
		).insert(ignore_permissions=True)

	options = _get_response_options(item_node, asset_map)
	correct_answers = set(_get_correct_answer_ids(item_node))
	if len(options) < 2 or len(options) > 4:
		return None

	question_doc = {
		"doctype": "LMS Question",
		"question": question_html,
		"type": "Choices",
	}
	for idx, option in enumerate(options, start=1):
		question_doc[f"option_{idx}"] = option["text"]
		question_doc[f"is_correct_{idx}"] = 1 if option["id"] in correct_answers else 0

	if not any(question_doc.get(f"is_correct_{idx}") for idx in range(1, len(options) + 1)):
		return None

	return frappe.get_doc(question_doc).insert(ignore_permissions=True)


def _get_qti_path(zip_file: zipfile.ZipFile, identifier: str, resources: dict) -> str | None:
	candidates = [
		f"{identifier}/assessment_qti.xml",
		f"non_cc_assessments/{identifier}.xml.qti",
	]

	resource = resources.get(identifier, {})
	candidates.extend(resource.get("files", []))
	for dependency in resource.get("dependencies", []):
		candidates.extend(resources.get(dependency, {}).get("files", []))

	for candidate in candidates:
		if candidate and candidate in zip_file.namelist() and candidate.endswith((".xml", ".qti")):
			return candidate

	return None


def _get_passing_percentage(zip_file: zipfile.ZipFile, identifier: str) -> int:
	meta_path = f"{identifier}/assessment_meta.xml"
	description = ""
	if meta_path in zip_file.namelist():
		meta_root = _read_xml(zip_file, meta_path)
		description = html.unescape(_text(meta_root, "description"))

	match = re.search(r"(\d{1,3})\s*%", description)
	if not match:
		return DEFAULT_PASSING_PERCENTAGE

	percentage = _safe_int(match.group(1), DEFAULT_PASSING_PERCENTAGE)
	return min(max(percentage, 0), 100)


def _get_qti_metadata(item_node, label: str) -> str:
	for field in _descendants(item_node, "qtimetadatafield"):
		if _text(field, "fieldlabel") == label:
			return _text(field, "fieldentry")

	return ""


def _get_question_text(item_node) -> str:
	presentation = _first_child(item_node, "presentation")
	material = _first_child(presentation, "material")
	mattext = _first_child(material, "mattext")
	return mattext.text or "" if mattext is not None else ""


def _get_question_marks(item_node) -> int:
	points = _get_qti_metadata(item_node, "points_possible")
	try:
		return max(int(float(points)), 1)
	except (TypeError, ValueError):
		return 1


def _get_response_options(item_node, asset_map: dict) -> list[dict]:
	options = []
	for response_label in _descendants(item_node, "response_label"):
		option_text = ""
		mattext = next(iter(_descendants(response_label, "mattext")), None)
		if mattext is not None and mattext.text:
			option_text = _replace_asset_refs(mattext.text, asset_map)

		if option_text:
			options.append({"id": response_label.attrib.get("ident"), "text": option_text})

	return options


def _get_correct_answer_ids(item_node) -> list[str]:
	return [node.text.strip() for node in _descendants(item_node, "varequal") if node.text]


def _clean_html(raw_html: str, asset_map: dict) -> str:
	body = _extract_body(raw_html)
	body = _replace_asset_refs(body, asset_map)
	body = _strip_canvas_attrs(body)
	body = _remove_escaped_tracks(body)
	body = _ensure_video_controls(body)
	body = _remove_canvas_query_strings(body)
	body = re.sub(r"\n{3,}", "\n\n", body)
	return body.strip()


def _extract_body(raw_html: str) -> str:
	match = re.search(r"<body[^>]*>(.*?)</body>", raw_html, flags=re.IGNORECASE | re.DOTALL)
	return match.group(1) if match else raw_html


def _replace_asset_refs(text: str, asset_map: dict) -> str:
	if not text:
		return ""

	for path, file_url in sorted(asset_map.items(), key=lambda row: len(row[0]), reverse=True):
		path_without_prefix = path.removeprefix(WEB_RESOURCE_PREFIX)
		variants = [
			f"{IMSCC_FILEBASE}{path_without_prefix}",
			f"{IMSCC_FILEBASE}{quote(path_without_prefix)}",
			f"{IMSCC_FILEBASE}{quote(path_without_prefix, safe='/')}",
			f"{IMSCC_FILEBASE}{quote(path_without_prefix, safe='/()&,')}",
			path,
			quote(path),
			quote(path, safe="/"),
			quote(path, safe="/()&,"),
			unquote(path),
			path_without_prefix,
			quote(path_without_prefix),
			quote(path_without_prefix, safe="/"),
			quote(path_without_prefix, safe="/()&,"),
			unquote(path_without_prefix),
			f"../{path_without_prefix}",
			f"../{quote(path_without_prefix, safe='/')}",
			f"../{quote(path_without_prefix, safe='/()&,')}",
		]
		variants.extend([html.escape(variant, quote=False) for variant in variants])
		variants = sorted(set(variants), key=len, reverse=True)
		for variant in variants:
			if variant:
				text = text.replace(variant, file_url)
	return text


def _strip_canvas_attrs(body: str) -> str:
	body = re.sub(r"\sdata-api-(?:endpoint|returntype)=(\"[^\"]*\"|'[^']*')", "", body)
	body = re.sub(r"\sdata-media-(?:id|type)=(\"[^\"]*\"|'[^']*')", "", body)
	body = re.sub(r"\sloading=(\"[^\"]*\"|'[^']*')", "", body)
	body = re.sub(r"\sclass=(\"instructure_file_link inline_disabled\"|'instructure_file_link inline_disabled')", "", body)
	return body


def _remove_escaped_tracks(body: str) -> str:
	return re.sub(r"&lt;track\b.*?/?&gt;", "", body, flags=re.IGNORECASE | re.DOTALL)


def _ensure_video_controls(body: str) -> str:
	def add_controls(match):
		tag = match.group(0)
		if re.search(r"\bcontrols\b", tag):
			return tag
		return tag[:-1] + ' controls controlsList="nodownload">'

	return re.sub(r"<video\b[^>]*>", add_controls, body, flags=re.IGNORECASE)


def _remove_canvas_query_strings(body: str) -> str:
	return re.sub(r"(\.(?:mp4|mp3|pdf|srt|png|jpe?g|gif|webp))\?canvas_[^\"'\s<>]+", r"\1", body)


def _extract_html_title(body: str) -> str:
	match = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.IGNORECASE | re.DOTALL)
	return html.unescape(match.group(1).strip()) if match else ""


def _is_quiz_item(content_type: str, resource: dict) -> bool:
	if content_type == "Quizzes::Quiz":
		return True

	resource_type = resource.get("type") or ""
	return "imsqti" in resource_type or "assessment" in resource_type


def _content_type_from_resource(resources: dict, identifier: str) -> str:
	resource_type = (resources.get(identifier, {}).get("type") or "").lower()
	if "imsqti" in resource_type or "assessment" in resource_type:
		return "Quizzes::Quiz"
	return "WikiPage"


def _title_from_resource(resources: dict, identifier: str) -> str:
	href = resources.get(identifier, {}).get("href")
	return _title_from_href(href)


def _title_from_href(href: str | None) -> str:
	if not href:
		return _("Untitled Lesson")

	name = os.path.splitext(os.path.basename(href))[0]
	name = unquote(name).replace("-dot-", ".").replace("-", " ")
	return name.strip().title() or _("Untitled Lesson")


def _safe_int(value, fallback: int) -> int:
	try:
		return int(value)
	except (TypeError, ValueError):
		return fallback
