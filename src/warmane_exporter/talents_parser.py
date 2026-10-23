"""Offline talents parser using structural HTML parsing for robustness."""
from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


def parse_talents_capture_file(path: Path) -> dict[str, Any]:
    """Parse a talents capture HTML file."""
    html = path.read_text(encoding="utf-8")
    return parse_talents_capture_html(html=html, source_name=str(path))


def parse_talents_capture_html(html: str, source_name: str = "<memory>") -> dict[str, Any]:
    """Parse talents capture HTML and extract specs, trees, talents, and glyphs."""
    if not html.strip():
        return {
            "parser_mode": "offline_rendered_dom_text_only",
            "source_name": source_name,
            "status": "failed",
            "error": "Empty input",
            "specs": [],
            "glyphs": {},
        }

    spec_tabs = _parse_spec_tabs_htmlparser(html)
    glyph_blocks = _parse_glyph_blocks_htmlparser(html)
    spec_containers = _parse_spec_containers_htmlparser(html)

    warnings: list[dict[str, Any]] = []
    
    if not spec_containers:
        return {
            "parser_mode": "offline_rendered_dom_text_only",
            "source_name": source_name,
            "status": "failed",
            "error": "No talent spec containers found",
            "specs": [],
            "glyphs": {},
        }

    # Fail only if there are no trees at all (completely empty specs)
    has_any_trees = any(len(container["trees"]) > 0 for container in spec_containers.values())
    if not has_any_trees:
        return {
            "parser_mode": "offline_rendered_dom_text_only",
            "source_name": source_name,
            "status": "failed",
            "error": "No talent trees found in spec containers",
            "specs": [],
            "glyphs": {},
            "warnings": warnings,
        }
    
    # Generate warnings for each spec and tree
    for spec_id, container in spec_containers.items():
        if spec_id not in spec_tabs:
            warnings.append({
                "type": "missing_spec_tab",
                "spec_id": spec_id,
                "message": f"Spec container {spec_id} found but no matching tab definition",
            })
        
        # Warn if spec container has no trees
        if not container["trees"]:
            warnings.append({
                "type": "spec_container_no_trees",
                "spec_id": spec_id,
                "message": f"Spec container {spec_id} found but contains no talent trees",
            })
        
        for tree in container["trees"]:
            check = _validate_tree_total(tree)
            if check["status"] == "mismatch":
                warnings.append({
                    "type": "tree_total_mismatch",
                    "spec_id": spec_id,
                    "tree_name": tree["name"],
                    "reported_total": tree["reported_total"],
                    "calculated_total": check["calculated_total"],
                    "message": f"Tree {tree['name']} reported total {tree['reported_total']} but selected talents sum to {check['calculated_total']}",
                })
            elif check["status"] == "indeterminate":
                warnings.append({
                    "type": "tree_total_indeterminate",
                    "spec_id": spec_id,
                    "tree_name": tree["name"],
                    "reason": check["reason"],
                    "message": f"Tree {tree['name']} total cannot be validated: {check['reason']}",
                })

    # Warn for spec tabs without matching containers
    for tab_id in spec_tabs:
        if tab_id not in spec_containers:
            warnings.append({
                "type": "missing_spec_container",
                "spec_id": tab_id,
                "message": f"Spec tab {tab_id} found but no matching container",
            })

    for glyph_spec_id in glyph_blocks:
        if glyph_spec_id not in spec_containers:
            warnings.append({
                "type": "missing_glyph_spec",
                "spec_id": glyph_spec_id,
                "message": f"Glyph block for spec {glyph_spec_id} found but no matching talent container",
            })
    
    # Warn if missing tabs, but don't fail (tabs are metadata, trees are data)
    if not spec_tabs:
        warnings.append({
            "type": "missing_all_spec_tabs",
            "message": "No spec tabs (data-spec attributes) found; tab structure unavailable",
        })

    status = "partial" if warnings else "complete"

    return {
        "parser_mode": "offline_rendered_dom_text_only",
        "source_name": source_name,
        "status": status,
        "active_spec_status": "unknown_not_determined_from_capture",
        "active_spec_notice": "In-game active specialization cannot be determined from rendered DOM. Selected UI tab and visibility state are capture metadata only, not character game state.",
        "specs": [
            {
                "source_spec_id": spec_id,
                "label": spec_tabs.get(spec_id, {}).get("label"),
                "capture_metadata": {
                    "ui_selected_class": spec_tabs.get(spec_id, {}).get("selected_class"),
                    "container_display_style": spec_containers[spec_id].get("display_style"),
                },
                "trees": spec_containers[spec_id]["trees"],
            }
            for spec_id in sorted(spec_containers.keys())
        ],
        "glyphs": {
            spec_id: {
                "source_spec_id": spec_id,
                "entries": glyphs,
            }
            for spec_id, glyphs in glyph_blocks.items()
        },
        "warnings": warnings,
        "summary": {
            "specs_found": len(spec_containers),
            "specs_with_glyph_blocks": len(glyph_blocks),
            "warnings_count": len(warnings),
        },
    }


def _parse_spec_tabs_htmlparser(html: str) -> dict[str, dict[str, Any]]:
    """Extract spec tab definitions and selection state using HTMLParser."""
    parser = SpecTabParser()
    parser.feed(html)
    return parser.tabs


class SpecTabParser(HTMLParser):
    """Parse spec tabs from <td data-spec="..."> elements."""
    
    def __init__(self) -> None:
        super().__init__()
        self.tabs: dict[str, dict[str, Any]] = {}
        self.in_tab_cell = False
        self.current_tab_id: str | None = None
        self.current_tab_classes: list[str] = []
        self.in_tab_link = False
        self.in_tab_img = False
        self.current_alt_text: str = ""
        self.tab_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: v for k, v in attrs if v is not None}
        
        if tag == "td" and "data-spec" in attrs_dict:
            self.current_tab_id = attrs_dict["data-spec"]
            self.current_tab_classes = attrs_dict.get("class", "").split()
            self.in_tab_cell = True
            self.tab_text_parts = []
        
        elif tag == "a" and self.in_tab_cell:
            self.in_tab_link = True
        
        elif tag == "img" and self.in_tab_link:
            self.in_tab_img = True
            self.current_alt_text = attrs_dict.get("alt", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_tab_cell:
            self.in_tab_cell = False
            if self.current_tab_id:
                label = self.current_alt_text or "".join(self.tab_text_parts).strip()
                class_str = " ".join(self.current_tab_classes)
                self.tabs[self.current_tab_id] = {
                    "label": label,
                    "selected_class": class_str,
                    "is_selected_in_capture": "selected" in self.current_tab_classes,
                }
            self.current_tab_id = None
            self.current_alt_text = ""
        
        elif tag == "a" and self.in_tab_link:
            self.in_tab_link = False
        
        elif tag == "img" and self.in_tab_img:
            self.in_tab_img = False

    def handle_data(self, data: str) -> None:
        if self.in_tab_link and not self.in_tab_img:
            text = data.strip()
            if text:
                self.tab_text_parts.append(text)


def _parse_glyph_blocks_htmlparser(html: str) -> dict[str, list[dict[str, Any]]]:
    """Extract glyph blocks using HTMLParser for class-order independence."""
    parser = GlyphBlockParser()
    parser.feed(html)
    return parser.glyphs


class GlyphBlockParser(HTMLParser):
    """Parse glyph blocks with unordered class attribute handling."""
    
    def __init__(self) -> None:
        super().__init__()
        self.glyphs: dict[str, list[dict[str, Any]]] = {}
        self.current_glyph_spec_id: str | None = None
        self.current_glyph_entries: list[dict[str, Any]] = []
        self.in_glyph_div = False
        self.glyph_category: str | None = None
        self.in_glyph_link = False
        self.current_glyph_href: str = ""
        self.glyph_name_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: v for k, v in attrs if v is not None}
        
        # Detect glyph block: <div data-glyphs="...">
        if tag == "div" and "data-glyphs" in attrs_dict:
            spec_id = attrs_dict["data-glyphs"]
            self.current_glyph_spec_id = spec_id
            self.current_glyph_entries = []
            if spec_id not in self.glyphs:
                self.glyphs[spec_id] = []
        
        # Detect individual glyph: <div class="glyph major/minor">
        elif tag == "div" and self.current_glyph_spec_id:
            classes = attrs_dict.get("class", "").split()
            if "glyph" in classes:
                self.in_glyph_div = True
                # Determine category from classes
                if "major" in classes:
                    self.glyph_category = "major"
                elif "minor" in classes:
                    self.glyph_category = "minor"
                else:
                    self.glyph_category = None
        
        # Detect glyph link: <a href="...spell=...">
        elif tag == "a" and self.in_glyph_div and "href" in attrs_dict:
            href = attrs_dict["href"]
            if "spell=" in href:
                self.in_glyph_link = True
                self.current_glyph_href = unescape(href)
                self.glyph_name_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.in_glyph_link:
            self.in_glyph_link = False
            # Create glyph entry
            if self.glyph_category and self.current_glyph_href:
                spell_match = re.search(r"spell=(\d+)", self.current_glyph_href)
                spell_id = spell_match.group(1) if spell_match else ""
                glyph_name = "".join(self.glyph_name_parts).strip()
                
                entry = {
                    "category": self.glyph_category,
                    "source_spell_id": spell_id,
                    "source_spell_href": self.current_glyph_href,
                    "name": glyph_name,
                    "spell_id_note": "Unresolved source spell reference; not yet verified as canonical glyph ID or effect-text mapping.",
                }
                self.current_glyph_entries.append(entry)
                self.glyph_name_parts = []
        
        elif tag == "div" and self.in_glyph_div:
            self.in_glyph_div = False
            self.glyph_category = None
        
        elif tag == "div" and self.current_glyph_spec_id:
            # Closing the glyph block - save entries
            if self.current_glyph_entries:
                self.glyphs[self.current_glyph_spec_id] = sorted(
                    self.current_glyph_entries, key=lambda e: (e["category"], e["name"])
                )
            self.current_glyph_spec_id = None

    def handle_data(self, data: str) -> None:
        if self.in_glyph_link:
            self.glyph_name_parts.append(data)


def _parse_spec_containers_htmlparser(html: str) -> dict[str, dict[str, Any]]:
    """Extract talent spec containers using HTMLParser for robust structural parsing."""
    parser = TalentSpecParser()
    parser.feed(html)
    return parser.containers


class TalentSpecParser(HTMLParser):
    """Parse talent specs, trees, and talent nodes with structural awareness."""
    
    def __init__(self) -> None:
        super().__init__()
        self.containers: dict[str, dict[str, Any]] = {}
        
        # Stack to track div nesting: list of (tag, class_list, div_id)
        self.div_stack: list[tuple[str, list[str], str]] = []
        
        # Current parsing state
        self.current_spec_id: str | None = None
        self.current_spec_display_style: str = ""
        self.current_tree: dict[str, Any] | None = None
        self.in_tree_info = False
        self.tree_info_parts: list[str] = []
        self.in_talent_anchor = False
        self.current_talent_href: str = ""
        self.current_talent_spell_id: str = ""
        self.in_talent_points_div = False
        self.rank_text_parts: list[str] = []
        self.has_talent_points_div = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: v for k, v in attrs if v is not None}
        
        if tag == "div":
            classes = attrs_dict.get("class", "").split()
            div_id = attrs_dict.get("id", "")
            
            # Track all divs on stack
            self.div_stack.append(("div", classes, div_id))
            
            # Detect spec container: <div id="spec-N" class="talents-container ...">
            if div_id.startswith("spec-"):
                spec_id = div_id.replace("spec-", "")
                self.current_spec_id = spec_id
                self.current_spec_display_style = attrs_dict.get("style", "")
                # Initialize container if not present
                if spec_id not in self.containers:
                    self.containers[spec_id] = {
                        "display_style": self.current_spec_display_style,
                        "trees": [],
                    }
            
            # Detect talent tree: <div class="talent-tree">
            elif "talent-tree" in classes and self.current_spec_id is not None:
                self.current_tree = {
                    "name": "",
                    "reported_total": None,
                    "talents": [],
                }
            
            # Detect tree info: <div class="talent-tree-info">
            elif "talent-tree-info" in classes and self.current_tree is not None:
                self.in_tree_info = True
                self.tree_info_parts = []
            
            # Detect talent points: <div class="talent-points ...">
            elif "talent-points" in classes and self.in_talent_anchor:
                self.in_talent_points_div = True
                self.has_talent_points_div = True
                self.rank_text_parts = []
        
        # Detect talent anchor: <a href="...spell=...">
        elif tag == "a" and "href" in attrs_dict:
            href = attrs_dict["href"]
            if "spell=" in href and self.current_tree is not None:
                self.in_talent_anchor = True
                self.current_talent_href = unescape(href)
                spell_match = re.search(r"spell=(\d+)", self.current_talent_href)
                self.current_talent_spell_id = spell_match.group(1) if spell_match else ""
                self.has_talent_points_div = False
                self.rank_text_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.div_stack:
            tag_name, classes, div_id = self.div_stack.pop()
            
            # Handle closing talent-points div
            if "talent-points" in classes and self.in_talent_points_div:
                self.in_talent_points_div = False
                rank_text = "".join(self.rank_text_parts).strip()
                
                # Parse rank text
                points_spent: int | None = None
                points_max: int | None = None
                rank_parse_error: str | None = None
                is_selected: bool | None = None
                
                if rank_text:
                    if "/" in rank_text:
                        parts = rank_text.split("/", 1)
                        try:
                            points_spent = int(parts[0].strip())
                            points_max = int(parts[1].strip())
                            if points_spent < 0 or points_max < 0 or points_spent > points_max:
                                rank_parse_error = f"Out of range: {points_spent}/{points_max}"
                                points_spent, points_max = None, None
                                is_selected = None
                            else:
                                is_selected = points_spent > 0
                        except ValueError as e:
                            rank_parse_error = str(e)
                            points_spent, points_max = None, None
                            is_selected = None
                    else:
                        rank_parse_error = f"No slash separator in rank text: {rank_text}"
                        is_selected = None
                else:
                    rank_parse_error = "Empty rank text"
                    is_selected = None
                
                if self.current_tree is not None:
                    talent = {
                        "source_spell_id": self.current_talent_spell_id,
                        "source_spell_href": self.current_talent_href,
                        "raw_rank_text": rank_text,
                        "points_spent": points_spent,
                        "points_max": points_max,
                        "is_selected": is_selected,
                        "rank_parse_error": rank_parse_error,
                        "spell_id_note": "Unresolved source spell reference; not yet verified as canonical talent ID or selected-rank spell ID.",
                    }
                    self.current_tree["talents"].append(talent)
            
            # Handle closing tree-info div
            elif "talent-tree-info" in classes and self.in_tree_info:
                self.in_tree_info = False
                if self.current_tree is not None:
                    info_text = " ".join(self.tree_info_parts)
                    # Extract tree name and total
                    name_match = re.search(r"^([A-Za-z\s]+?)(?:\s*&nbsp;)?\s*(\d+)\s*$", info_text)
                    if name_match:
                        self.current_tree["name"] = name_match.group(1).strip()
                        self.current_tree["reported_total"] = int(name_match.group(2))
                    else:
                        # Unparseable tree info
                        if info_text:
                            self.current_tree["name"] = info_text
                            # reported_total stays None to trigger indeterminate validation
            
            # Handle closing talent-tree div
            elif "talent-tree" in classes and self.current_tree is not None:
                if self.current_spec_id is not None:
                    self.containers[self.current_spec_id]["trees"].append(self.current_tree)
                self.current_tree = None
            
            # Handle closing spec container div
            elif div_id.startswith("spec-"):
                self.current_spec_id = None
        
        # Handle closing talent anchor - finalize talent if no rank was captured
        elif tag == "a" and self.in_talent_anchor:
            self.in_talent_anchor = False
            
            # If anchor closes without a talent-points div, create talent with null rank
            if not self.has_talent_points_div and self.current_tree is not None:
                talent = {
                    "source_spell_id": self.current_talent_spell_id,
                    "source_spell_href": self.current_talent_href,
                    "raw_rank_text": None,
                    "points_spent": None,
                    "points_max": None,
                    "is_selected": None,
                    "rank_parse_error": "No talent-points element found in anchor",
                    "spell_id_note": "Unresolved source spell reference; not yet verified as canonical talent ID or selected-rank spell ID.",
                }
                self.current_tree["talents"].append(talent)
            
            self.current_talent_href = ""
            self.current_talent_spell_id = ""
            self.rank_text_parts = []

    def handle_data(self, data: str) -> None:
        """Accumulate text data."""
        if self.in_tree_info:
            text = data.strip()
            if text:
                self.tree_info_parts.append(text)
        elif self.in_talent_points_div:
            self.rank_text_parts.append(data)


def _validate_tree_total(tree: dict[str, Any]) -> dict[str, Any]:
    """Validate a tree's reported total against selected talent sum."""
    calculated_sum = 0
    has_parse_error = False
    
    # If reported_total is None (unparseable), validation is indeterminate
    if tree["reported_total"] is None:
        return {
            "status": "indeterminate",
            "reason": "Tree reported total is unknown/unparseable",
        }

    for talent in tree["talents"]:
        if talent["rank_parse_error"]:
            has_parse_error = True
        elif talent["points_spent"] is not None:
            calculated_sum += talent["points_spent"]

    if has_parse_error:
        return {
            "status": "indeterminate",
            "reason": "One or more talent ranks could not be parsed",
        }

    if calculated_sum == tree["reported_total"]:
        return {
            "status": "match",
            "calculated_total": calculated_sum,
        }
    else:
        return {
            "status": "mismatch",
            "calculated_total": calculated_sum,
            "reported_total": tree["reported_total"],
        }
