"""Canvas IMSCC import helpers for Frappe LMS."""

from __future__ import annotations

import html
import os
import posixpath
import re
import zipfile
from urllib.parse import quote, unquote
import xml.etree.ElementTree as ET

import frappe
from frappe import _
from frappe.utils.file_manager import is_safe_path

from lms.lms.utils import get_lesson_count, get_lesson_index, get_lesson_url


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
		resource_lessons = {}

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
					if item.get("identifierref"):
						resource_lessons[item["identifierref"]] = lesson.name

		_rewrite_internal_lesson_links(course.name, resource_lessons)
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
			"attributes": dict(resource.attrib),
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
		return _with_front_page_items(zip_file, resources, modules)

	modules = _get_modules_from_manifest(zip_file, resources)
	if modules:
		return _with_front_page_items(zip_file, resources, modules)

	return _with_front_page_items(zip_file, resources, _get_modules_from_wiki_resources(resources))


def _with_front_page_items(
	zip_file: zipfile.ZipFile, resources: dict, modules: list[dict]
) -> list[dict]:
	front_page_items = _get_unlisted_front_page_items(zip_file, resources, modules)
	if not front_page_items:
		return modules

	if not modules:
		modules = [{"title": _("Course Content"), "position": 1, "items": []}]

	first_module = modules[0]
	first_module["items"] = [
		*front_page_items,
		*(first_module.get("items") or []),
	]
	for idx, item in enumerate(first_module["items"], start=1):
		item["position"] = idx

	return modules


def _get_unlisted_front_page_items(
	zip_file: zipfile.ZipFile, resources: dict, modules: list[dict]
) -> list[dict]:
	referenced_identifiers = {
		item.get("identifierref")
		for module in modules
		for item in module.get("items", [])
		if item.get("identifierref")
	}
	front_page_items = []

	for identifier, resource in resources.items():
		if identifier in referenced_identifiers:
			continue

		href = resource.get("href")
		if not href or href not in zip_file.namelist():
			continue

		if resource.get("type") != "webcontent" or not href.startswith("wiki_content/"):
			continue

		raw_html = _read_text(zip_file, href)
		if not _is_canvas_front_page(raw_html):
			continue

		front_page_items.append(
			{
				"title": _extract_html_title(raw_html) or _title_from_href(href),
				"identifierref": identifier,
				"content_type": "WikiPage",
				"position": len(front_page_items) + 1,
			}
		)

	return front_page_items


def _is_canvas_front_page(raw_html: str) -> bool:
	for meta_tag in re.findall(r"<meta\b[^>]*>", raw_html, flags=re.IGNORECASE):
		attributes = {
			name.lower(): value.strip().lower()
			for name, _quote, value in re.findall(
				r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(['\"])(.*?)\2",
				meta_tag,
				flags=re.IGNORECASE | re.DOTALL,
			)
		}
		if attributes.get("name") == "front_page" and attributes.get("content") in {"true", "1"}:
			return True

	return False


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
					"url": _text(item, "url"),
					"html_url": _text(item, "html_url"),
					"new_tab": _text(item, "new_tab"),
					"indent": _safe_int(_text(item, "indent"), 0),
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
	if organization is None:
		return []

	modules = []
	loose_items = []
	for top_level_item in _children(organization, "item"):
		child_items = _manifest_leaf_items(top_level_item, resources)
		if child_items:
			modules.append(
				{
					"title": _text(top_level_item, "title") or _("Course Content"),
					"position": len(modules) + 1,
					"items": child_items,
				}
			)
			continue

		row = _manifest_item_row(top_level_item, resources, len(loose_items) + 1)
		if row:
			loose_items.append(row)

	if loose_items:
		modules.insert(
			0,
			{"title": _("Course Content"), "position": 1, "items": loose_items},
		)
		for position, module in enumerate(modules, start=1):
			module["position"] = position

	return modules


def _manifest_leaf_items(parent, resources: dict) -> list[dict]:
	items = []
	for item in _children(parent, "item"):
		nested_items = _children(item, "item")
		if nested_items:
			items.extend(_manifest_leaf_items(item, resources))
			continue

		row = _manifest_item_row(item, resources, len(items) + 1)
		if row:
			items.append(row)

	return items


def _manifest_item_row(item, resources: dict, position: int) -> dict | None:
	identifierref = item.attrib.get("identifierref")
	if not identifierref:
		return None

	return {
		"title": _text(item, "title") or _title_from_resource(resources, identifierref),
		"identifierref": identifierref,
		"content_type": _content_type_from_resource(resources, identifierref),
		"position": position,
	}


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
	href = _get_resource_html_path(zip_file, resource, resources)
	if href:
		body = _clean_html(_read_text(zip_file, href), asset_map, href)
	elif external_url := _get_external_resource_url(zip_file, item, resource):
		body = _build_external_resource_body(external_url, item.get("title"))
	elif asset_url := _get_resource_asset_url(resource, resources, asset_map):
		body = _build_attachment_body(asset_url, item.get("title"))
	else:
		return None

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


def _get_resource_html_path(zip_file: zipfile.ZipFile, resource: dict, resources: dict) -> str | None:
	for candidate in _get_resource_files(resource, resources):
		if not candidate or candidate not in zip_file.namelist():
			continue
		if candidate.lower().endswith((".html", ".htm")):
			return candidate

	return None


def _get_resource_files(resource: dict, resources: dict) -> list[str]:
	files = [resource.get("href"), *resource.get("files", [])]
	for dependency in resource.get("dependencies", []):
		dependency_resource = resources.get(dependency, {})
		files.extend([dependency_resource.get("href"), *dependency_resource.get("files", [])])
	return [path for path in dict.fromkeys(files) if path]


def _get_external_resource_url(zip_file: zipfile.ZipFile, item: dict, resource: dict) -> str | None:
	for value in (item.get("url"), item.get("html_url"), resource.get("href")):
		if _is_external_url(value):
			return value

	content_type = (item.get("content_type") or "").lower()
	resource_type = (resource.get("type") or "").lower()
	if not any(token in f"{content_type} {resource_type}" for token in ("external", "imswl", "imslticc")):
		return None

	for path in [resource.get("href"), *resource.get("files", [])]:
		if not path or not path.lower().endswith((".xml", ".imswl", ".imslticc")):
			continue
		root = _read_xml(zip_file, path) if path else None
		for node in root.iter() if root is not None else []:
			if _local_name(node.tag) not in {"url", "launch_url", "secure_launch_url"}:
				continue
			value = node.attrib.get("href") or (node.text or "").strip()
			if _is_external_url(value):
				return value

	return None


def _get_resource_asset_url(resource: dict, resources: dict, asset_map: dict) -> str | None:
	for path in _get_resource_files(resource, resources):
		if path in asset_map:
			return asset_map[path]
	return None


def _build_external_resource_body(url: str, title: str | None = None) -> str:
	safe_url = html.escape(url, quote=True)
	safe_title = html.escape(title or _("Open external content"), quote=True)
	if _is_embeddable_url(url):
		return (
			f'<iframe src="{safe_url}" title="{safe_title}" width="100%" height="720" '
			'loading="lazy" allowfullscreen '
			'allow="autoplay *; geolocation *; microphone *; camera *; midi *; encrypted-media *">'
			"</iframe>"
		)

	return (
		f'<p><a href="{safe_url}" target="_blank" rel="noopener noreferrer">'
		f"{safe_title}</a></p>"
	)


def _build_attachment_body(file_url: str, title: str | None = None) -> str:
	safe_url = html.escape(file_url, quote=True)
	safe_title = html.escape(title or _("Course attachment"), quote=True)
	extension = os.path.splitext(file_url.split("?", 1)[0])[1].lower()

	if extension in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
		return f'<p><img src="{safe_url}" alt="{safe_title}"></p>'
	if extension in {".mp4", ".webm", ".ogg"}:
		return f'<video controls width="100%"><source src="{safe_url}"></video>'
	if extension in {".mp3", ".wav", ".m4a", ".aac"}:
		return f'<audio controls width="100%"><source src="{safe_url}"></audio>'
	if extension == ".pdf":
		return f'<iframe src="{safe_url}" title="{safe_title}" width="100%" height="720"></iframe>'

	return (
		f'<p><a href="{safe_url}" target="_blank" rel="noopener noreferrer" download>'
		f"{safe_title}</a></p>"
	)


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


def _clean_html(raw_html: str, asset_map: dict, source_path: str | None = None) -> str:
	body = _extract_body(raw_html)
	body = _replace_asset_refs(body, asset_map)
	body = _replace_relative_asset_refs(body, source_path, asset_map)
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
			f"../{path}",
			f"../{quote(path, safe='/')}",
			f"../{quote(path, safe='/()&,')}",
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


def _replace_relative_asset_refs(text: str, source_path: str | None, asset_map: dict) -> str:
	if not text or not asset_map:
		return text

	attribute_pattern = re.compile(
		r"(?P<prefix>\b(?:src|href|poster|data)\s*=\s*)(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
		flags=re.IGNORECASE | re.DOTALL,
	)

	def replace_attribute(match):
		value = match.group("value")
		resolved = _resolve_asset_reference(value, source_path, asset_map)
		return f"{match.group('prefix')}{match.group('quote')}{resolved}{match.group('quote')}"

	text = attribute_pattern.sub(replace_attribute, text)

	def replace_css_url(match):
		quote_char = match.group("quote") or ""
		value = match.group("value")
		resolved = _resolve_asset_reference(value, source_path, asset_map)
		return f"url({quote_char}{resolved}{quote_char})"

	return re.sub(
		r"url\(\s*(?P<quote>[\"']?)(?P<value>.*?)(?P=quote)\s*\)",
		replace_css_url,
		text,
		flags=re.IGNORECASE,
	)


def _resolve_asset_reference(value: str, source_path: str | None, asset_map: dict) -> str:
	decoded_value = html.unescape(value).strip()
	if (
		not decoded_value
		or decoded_value.startswith(("#", "/", "data:", "mailto:", "tel:", "{{", "$WIKI_REFERENCE$"))
		or _is_external_url(decoded_value)
	):
		return value

	path_part, separator, fragment = decoded_value.partition("#")
	path_part = path_part.split("?", 1)[0]
	path_part = unquote(path_part)

	candidates = []
	if path_part.startswith(IMSCC_FILEBASE):
		candidates.append(f"{WEB_RESOURCE_PREFIX}{path_part.removeprefix(IMSCC_FILEBASE).lstrip('/')}")
	else:
		candidates.append(path_part)
		if source_path:
			candidates.append(posixpath.normpath(posixpath.join(posixpath.dirname(source_path), path_part)))
		candidates.append(f"{WEB_RESOURCE_PREFIX}{path_part.lstrip('../')}")

	for candidate in candidates:
		normalized = posixpath.normpath(candidate)
		if normalized in asset_map:
			suffix = f"#{fragment}" if separator else ""
			return f"{asset_map[normalized]}{suffix}"

	return value


def _strip_canvas_attrs(body: str) -> str:
	body = re.sub(r"\sdata-api-(?:endpoint|returntype)=(\"[^\"]*\"|'[^']*')", "", body)
	body = re.sub(r"\sdata-media-(?:id|type)=(\"[^\"]*\"|'[^']*')", "", body)
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


def _rewrite_internal_lesson_links(course_name: str, resource_lessons: dict[str, str]) -> None:
	if not resource_lessons:
		return

	resource_urls = {
		identifier: get_lesson_url(course_name, get_lesson_index(lesson_name))
		for identifier, lesson_name in resource_lessons.items()
	}
	for lesson_name in resource_lessons.values():
		body = frappe.db.get_value("Course Lesson", lesson_name, "body") or ""
		updated_body = body
		for identifier, lesson_url in resource_urls.items():
			updated_body = re.sub(
				rf"\$WIKI_REFERENCE\$/pages/{re.escape(identifier)}(?=[\"'#?])",
				lesson_url,
				updated_body,
			)
		if updated_body != body:
			frappe.db.set_value(
				"Course Lesson",
				lesson_name,
				"body",
				updated_body,
				update_modified=False,
			)


def _is_external_url(value: str | None) -> bool:
	return bool(value and re.match(r"^https?://", value, flags=re.IGNORECASE))


def _is_embeddable_url(url: str) -> bool:
	return bool(
		re.search(
			r"(?:youtube\.com|youtu\.be|vimeo\.com|h5p\.com|docs\.google\.com/presentation|"
			r"mentimeter\.com|menti\.com)",
			url,
			flags=re.IGNORECASE,
		)
	)


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
