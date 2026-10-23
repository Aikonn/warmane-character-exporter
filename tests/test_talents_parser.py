from pathlib import Path
import unittest

from warmane_exporter.talents_parser import parse_talents_capture_file, parse_talents_capture_html


class TalentsParserTests(unittest.TestCase):
    def test_parses_synthetic_talents_page_structure(self) -> None:
        html = Path("tests/fixtures/synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_talents_capture_html(html, source_name="synthetic-talents")

        self.assertEqual(result["parser_mode"], "offline_rendered_dom_text_only")
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["active_spec_status"], "unknown_not_determined_from_capture")
        self.assertIn("in-game active specialization cannot be determined", result["active_spec_notice"].lower())

        specs = result["specs"]
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0]["source_spec_id"], "0")
        self.assertEqual(specs[0]["label"], "Discipline")
        self.assertEqual(specs[1]["source_spec_id"], "1")
        self.assertEqual(specs[1]["label"], "Holy")

    def test_both_hidden_and_visible_specs_parsed(self) -> None:
        html = Path("tests/fixtures/synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_talents_capture_html(html, source_name="synthetic-talents")

        specs = {spec["source_spec_id"]: spec for spec in result["specs"]}
        self.assertIn("0", specs)
        self.assertIn("1", specs)

        # spec 0 should be visible in capture
        self.assertEqual(specs["0"]["capture_metadata"]["container_display_style"], "display: block;")
        # spec 1 should be hidden in capture
        self.assertEqual(specs["1"]["capture_metadata"]["container_display_style"], "display: none;")

    def test_parses_trees_and_talents_per_spec(self) -> None:
        html = Path("tests/fixtures/synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_talents_capture_html(html, source_name="synthetic-talents")

        spec0 = result["specs"][0]
        trees0 = spec0["trees"]
        self.assertEqual(len(trees0), 3)

        discipline = next((t for t in trees0 if t["name"] == "Discipline"), None)
        self.assertIsNotNone(discipline)
        self.assertEqual(discipline["reported_total"], 5)
        self.assertGreater(len(discipline["talents"]), 0)

        holy = next((t for t in trees0 if t["name"] == "Holy"), None)
        self.assertIsNotNone(holy)
        self.assertEqual(holy["reported_total"], 2)

        shadow = next((t for t in trees0 if t["name"] == "Shadow"), None)
        self.assertIsNotNone(shadow)
        self.assertEqual(shadow["reported_total"], 0)

    def test_selected_vs_unselected_talents(self) -> None:
        html = Path("tests/fixtures/synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_talents_capture_html(html, source_name="synthetic-talents")

        spec0 = result["specs"][0]
        discipline = next((t for t in spec0["trees"] if t["name"] == "Discipline"), None)
        talents = discipline["talents"]

        selected_talents = [t for t in talents if t["is_selected"]]
        unselected_talents = [t for t in talents if t["is_selected"] is False]

        self.assertGreater(len(selected_talents), 0)
        self.assertGreater(len(unselected_talents), 0)

        for talent in selected_talents:
            self.assertGreater(talent["points_spent"], 0)
            self.assertIsNotNone(talent["source_spell_id"])

        for talent in unselected_talents:
            self.assertEqual(talent["points_spent"], 0)

    def test_talent_attributes_preserved(self) -> None:
        html = Path("tests/fixtures/synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_talents_capture_html(html, source_name="synthetic-talents")

        spec0 = result["specs"][0]
        discipline = next((t for t in spec0["trees"] if t["name"] == "Discipline"), None)
        talents = discipline["talents"]

        for talent in talents:
            self.assertIsNotNone(talent["source_spell_id"])
            self.assertIsNotNone(talent["source_spell_href"])
            self.assertIn("spell=", talent["source_spell_href"])
            self.assertIsNotNone(talent["raw_rank_text"])
            self.assertIsNotNone(talent["points_spent"])
            self.assertIsNotNone(talent["points_max"])
            self.assertIsNotNone(talent["is_selected"])
            self.assertIn("unresolved", talent.get("spell_id_note", "").lower())

    def test_glyph_associations_by_spec(self) -> None:
        html = Path("tests/fixtures/synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_talents_capture_html(html, source_name="synthetic-talents")

        glyphs = result["glyphs"]
        self.assertIn("0", glyphs)
        self.assertIn("1", glyphs)

        glyph_spec0 = glyphs["0"]["entries"]
        glyph_spec1 = glyphs["1"]["entries"]

        self.assertEqual(len(glyph_spec0), 3)
        self.assertEqual(len(glyph_spec1), 2)

        major0 = [g for g in glyph_spec0 if g["category"] == "major"]
        minor0 = [g for g in glyph_spec0 if g["category"] == "minor"]
        self.assertEqual(len(major0), 2)
        self.assertEqual(len(minor0), 1)

    def test_glyph_attributes_preserved(self) -> None:
        html = Path("tests/fixtures/synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_talents_capture_html(html, source_name="synthetic-talents")

        glyphs = result["glyphs"]["0"]["entries"]
        for glyph in glyphs:
            self.assertIsNotNone(glyph["category"])
            self.assertIsNotNone(glyph["source_spell_id"])
            self.assertIsNotNone(glyph["source_spell_href"])
            self.assertIn("spell=", glyph["source_spell_href"])
            self.assertIsNotNone(glyph["name"])
            self.assertIn("unresolved", glyph.get("spell_id_note", "").lower())

    def test_tree_total_match(self) -> None:
        html = Path("tests/fixtures/synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_talents_capture_html(html, source_name="synthetic-talents")

        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["warnings"]), 0)

    def test_empty_input_fails(self) -> None:
        result = parse_talents_capture_html("", source_name="empty")
        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result)

    def test_unrecognized_input_fails(self) -> None:
        result = parse_talents_capture_html("<html><body>No talents here</body></html>", source_name="invalid")
        self.assertEqual(result["status"], "failed")
        self.assertIn("No talent spec containers found", result.get("error", ""))

    def test_talent_points_without_secondary_class(self) -> None:
        """Regression test for talents with class="talent-points" (no secondary class like 'disabled')"""
        html = """
        <table class="talent-spec-switch">
            <tr>
                <td data-spec="0"><a><img alt="Test" /></a></td>
            </tr>
        </table>
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>8</span>
                </div>
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=100" class="talent col1">
                        <div class="talent-points disabled">0/3</div>
                    </a>
                    <a href="//wotlk.cavernoftime.com/spell=101" class="talent col2">
                        <div class="talent-points">3/5</div>
                    </a>
                    <a href="//wotlk.cavernoftime.com/spell=102" class="talent col3">
                        <div class="talent-points max">5/5</div>
                    </a>
                </div>
            </div>
        </div>
        <div class="clear"></div>
        <script></script>
        """
        result = parse_talents_capture_html(html, source_name="regression-test")
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["warnings"]), 0)

        tree = result["specs"][0]["trees"][0]
        self.assertEqual(tree["reported_total"], 8)
        self.assertEqual(len(tree["talents"]), 3)

        # Verify all talents extracted including one with no secondary class
        spell_ids = sorted([t["source_spell_id"] for t in tree["talents"]])
        self.assertEqual(spell_ids, ["100", "101", "102"])

        # Verify point totals match
        points_sum = sum(t["points_spent"] for t in tree["talents"] if t["points_spent"] is not None)
        self.assertEqual(points_sum, 8)

        # Verify selected talents
        selected = [t for t in tree["talents"] if t["is_selected"]]
        self.assertEqual(len(selected), 2)  # Spells 101 and 102 are selected
        selected_ids = sorted([t["source_spell_id"] for t in selected])
        self.assertEqual(selected_ids, ["101", "102"])

    def test_no_tooltip_effect_text_extracted(self) -> None:
        html = Path("tests/fixtures/synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_talents_capture_html(html, source_name="synthetic-talents")

        talents_list = result["specs"][0]["trees"][0]["talents"]
        for talent in talents_list:
            self.assertNotIn("effect_text", talent)
            self.assertNotIn("tooltip", talent)

    def test_malformed_ranks_preserved_as_errors(self) -> None:
        html = """
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>1</span>
                </div>
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=123" class="talent col1">
                        <div class="talent-points disabled">bad/5</div>
                    </a>
                    <a href="//wotlk.cavernoftime.com/spell=124" class="talent col2">
                        <div class="talent-points disabled">2/bad</div>
                    </a>
                </div>
            </div>
        </div>
        <div class="clear"></div>
        <script></script>
        """
        result = parse_talents_capture_html(html, source_name="malformed-test")
        self.assertEqual(result["status"], "partial")
        self.assertGreater(len(result["warnings"]), 0)

        tree = result["specs"][0]["trees"][0]
        malformed_talents = [t for t in tree["talents"] if t["rank_parse_error"]]
        self.assertEqual(len(malformed_talents), 2)

        for talent in malformed_talents:
            self.assertIsNone(talent["points_spent"])
            self.assertIsNone(talent["points_max"])
            self.assertIsNone(talent["is_selected"])
            self.assertIsNotNone(talent["rank_parse_error"])

    def test_tree_total_mismatch_warning(self) -> None:
        html = """
        <table class="talent-spec-switch">
            <tr>
                <td data-spec="0"><a><img alt="Test" /></a></td>
            </tr>
        </table>
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>10</span>
                </div>
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=123" class="talent col1">
                        <div class="talent-points max">5/5</div>
                    </a>
                </div>
            </div>
        </div>
        <div class="clear"></div>
        <script></script>
        """
        result = parse_talents_capture_html(html, source_name="mismatch-test")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(result["warnings"][0]["type"], "tree_total_mismatch")

    def test_tree_total_indeterminate_when_parse_error(self) -> None:
        html = """
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>5</span>
                </div>
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=123" class="talent col1">
                        <div class="talent-points max">bad/5</div>
                    </a>
                    <a href="//wotlk.cavernoftime.com/spell=124" class="talent col2">
                        <div class="talent-points max">2/5</div>
                    </a>
                </div>
            </div>
        </div>
        <div class="clear"></div>
        <script></script>
        """
        result = parse_talents_capture_html(html, source_name="indeterminate-test")
        self.assertEqual(result["status"], "partial")
        warnings = result["warnings"]
        indeterminate = [w for w in warnings if w["type"] == "tree_total_indeterminate"]
        self.assertEqual(len(indeterminate), 1)

    def test_parse_from_file(self) -> None:
        result = parse_talents_capture_file(Path("tests/fixtures/synthetic/talents-page-dom-synthetic.html"))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["specs"]), 2)

    def test_spec_container_without_trees_fails(self) -> None:
        """Regression: spec container with no trees must fail, not return complete."""
        html = """
        <table class="talent-spec-switch">
        <tr><td data-spec="0"><a><img alt="Test" /></a></td></tr>
        </table>
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
        </div>
        <div class="clear"></div>
        <script></script>
        """
        result = parse_talents_capture_html(html, source_name="container-no-trees-test")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["specs"]), 0)
        # Error should mention "trees" or "no talent trees"
        error = result.get("error", "").lower()
        self.assertTrue("trees" in error or "no trees" in error or "talent trees" in error)

    def test_malformed_rank_without_slash_preserved(self) -> None:
        """Regression: talent with malformed rank (no slash) must be retained with error."""
        html = """
        <table class="talent-spec-switch">
        <tr><td data-spec="0"><a><img alt="Test" /></a></td></tr>
        </table>
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>0</span>
                </div>
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=100" class="talent col1">
                        <div class="talent-points">bad</div>
                    </a>
                </div>
            </div>
        </div>
        <div class="clear"></div>
        <script></script>
        """
        result = parse_talents_capture_html(html, source_name="malformed-rank-test")
        
        # Must return partial, not complete
        self.assertEqual(result["status"], "partial")
        
        # Tree must exist and contain the talent
        self.assertEqual(len(result["specs"]), 1)
        tree = result["specs"][0]["trees"][0]
        
        # Talent must NOT be silently omitted
        self.assertEqual(len(tree["talents"]), 1)
        
        talent = tree["talents"][0]
        # Preserve raw rank text
        self.assertEqual(talent["raw_rank_text"], "bad")
        # Mark rank as unparseable
        self.assertIsNotNone(talent["rank_parse_error"])
        self.assertIn("slash", talent["rank_parse_error"].lower())
        # Set parsed values to None
        self.assertIsNone(talent["points_spent"])
        self.assertIsNone(talent["points_max"])
        self.assertIsNone(talent["is_selected"])

    def test_attribute_order_independence(self) -> None:
        """Test that style attribute can come before or after class, etc."""
        html_style_first = """
        <table class="talent-spec-switch">
        <tr><td data-spec="0"><a><img alt="Test" /></a></td></tr>
        </table>
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>1</span>
                </div>
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=100" class="talent">
                        <div class="talent-points">1/1</div>
                    </a>
                </div>
            </div>
        </div>
        """
        html_style_last = """
        <table class="talent-spec-switch">
        <tr><td data-spec="0" class="selected"><a><img alt="Test" /></a></td></tr>
        </table>
        <div style="display: block;" id="spec-0" class="talents-container wotlk">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>1</span>
                </div>
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=100" class="talent">
                        <div class="talent-points">1/1</div>
                    </a>
                </div>
            </div>
        </div>
        """
        
        result1 = parse_talents_capture_html(html_style_first, source_name="test1")
        result2 = parse_talents_capture_html(html_style_last, source_name="test2")
        
        self.assertEqual(result1["status"], "complete")
        self.assertEqual(result2["status"], "complete")
        self.assertEqual(len(result1["specs"]), 1)
        self.assertEqual(len(result2["specs"]), 1)
        self.assertEqual(result1["specs"][0]["trees"][0]["talents"][0]["source_spell_id"], "100")
        self.assertEqual(result2["specs"][0]["trees"][0]["talents"][0]["source_spell_id"], "100")

    def test_raw_rank_text_preserved_for_valid_ranks(self) -> None:
        """Test that raw_rank_text is preserved even for valid ranks."""
        html = """
        <table class="talent-spec-switch">
        <tr><td data-spec="0"><a><img alt="Test" /></a></td></tr>
        </table>
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>5</span>
                </div>
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=100" class="talent">
                        <div class="talent-points">2/5</div>
                    </a>
                    <a href="//wotlk.cavernoftime.com/spell=101" class="talent">
                        <div class="talent-points">3/3</div>
                    </a>
                </div>
            </div>
        </div>
        """
        result = parse_talents_capture_html(html, source_name="raw-text-test")
        
        self.assertEqual(result["status"], "complete")
        talents = result["specs"][0]["trees"][0]["talents"]
        
        self.assertEqual(talents[0]["raw_rank_text"], "2/5")
        self.assertEqual(talents[0]["points_spent"], 2)
        self.assertIsNone(talents[0]["rank_parse_error"])
        
        self.assertEqual(talents[1]["raw_rank_text"], "3/3")
        self.assertEqual(talents[1]["points_spent"], 3)
        self.assertIsNone(talents[1]["rank_parse_error"])

    def test_talent_anchor_without_talent_points_div_retained(self) -> None:
        """Regression: talent anchor without talent-points element must be retained with error."""
        html = """
        <table class="talent-spec-switch">
        <tr><td data-spec="0"><a><img alt="Test" /></a></td></tr>
        </table>
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>0</span>
                </div>
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=100" class="talent">
                    </a>
                </div>
            </div>
        </div>
        """
        result = parse_talents_capture_html(html, source_name="anchor-no-points-test")
        
        # Status should be partial (warning about missing rank div)
        self.assertEqual(result["status"], "partial")
        
        # Talent must be retained
        talents = result["specs"][0]["trees"][0]["talents"]
        self.assertEqual(len(talents), 1)
        
        talent = talents[0]
        self.assertEqual(talent["source_spell_id"], "100")
        self.assertIsNone(talent["raw_rank_text"])
        self.assertIsNone(talent["points_spent"])
        self.assertIsNone(talent["points_max"])
        self.assertIsNone(talent["is_selected"])
        self.assertIn("talent-points", talent["rank_parse_error"].lower())

    def test_tree_without_tree_info_indeterminate(self) -> None:
        """Regression: tree without tree-info should have unknown reported_total and indeterminate validation."""
        html = """
        <table class="talent-spec-switch">
        <tr><td data-spec="0"><a><img alt="Test" /></a></td></tr>
        </table>
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=100" class="talent">
                        <div class="talent-points">2/5</div>
                    </a>
                </div>
            </div>
        </div>
        """
        result = parse_talents_capture_html(html, source_name="tree-no-info-test")
        
        # Should return partial with warning about tree-total being indeterminate
        self.assertEqual(result["status"], "partial")
        self.assertGreater(len(result["warnings"]), 0)
        
        tree = result["specs"][0]["trees"][0]
        self.assertIsNone(tree["reported_total"])
        
        # Validation should be indeterminate
        indeterminate_warnings = [w for w in result["warnings"] if w["type"] == "tree_total_indeterminate"]
        self.assertGreater(len(indeterminate_warnings), 0)

    def test_spec_tab_without_matching_container_warned(self) -> None:
        """Regression: spec tab without matching container should be warned."""
        html = """
        <table class="talent-spec-switch">
        <tr>
            <td data-spec="0"><a><img alt="Spec0" /></a></td>
            <td data-spec="1"><a><img alt="Spec1" /></a></td>
        </tr>
        </table>
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>1</span>
                </div>
                <div class="tier">
                    <a href="//wotlk.cavernoftime.com/spell=100" class="talent">
                        <div class="talent-points">1/1</div>
                    </a>
                </div>
            </div>
        </div>
        """
        result = parse_talents_capture_html(html, source_name="tab-no-container-test")
        
        # Should return partial with warning
        self.assertEqual(result["status"], "partial")
        
        # Find warning about missing spec 1 container
        missing_container_warnings = [w for w in result["warnings"] if w["type"] == "missing_spec_container"]
        self.assertEqual(len(missing_container_warnings), 1)
        self.assertEqual(missing_container_warnings[0]["spec_id"], "1")

    def test_glyph_class_order_independence(self) -> None:
        """Regression: glyph divs with class order \"glyph major\" and \"major glyph\" both parse."""
        html = """
        <div class="character-glyphs">
            <div data-glyphs="0">
                <div class="glyph major">
                    <a href="http://wotlk.cavernoftime.com/spell=55679">Glyph One</a>
                </div>
                <div class="major glyph">
                    <a href="http://wotlk.cavernoftime.com/spell=55680">Glyph Two</a>
                </div>
                <div class="minor glyph">
                    <a href="http://wotlk.cavernoftime.com/spell=55681">Glyph Three</a>
                </div>
            </div>
        </div>
        <table class="talent-spec-switch">
        <tr><td data-spec="0"><a><img alt="Test" /></a></td></tr>
        </table>
        <div id="spec-0" class="talents-container wotlk" style="display: block;">
            <div class="talent-tree">
                <div class="talent-tree-info">
                    <span>Test</span> &nbsp;<span>0</span>
                </div>
            </div>
        </div>
        """
        result = parse_talents_capture_html(html, source_name="glyph-order-test")
        
        # Should parse both "glyph major" and "major glyph" formats
        glyphs = result["glyphs"].get("0", {}).get("entries", [])
        self.assertEqual(len(glyphs), 3)
        
        spell_ids = sorted([g["source_spell_id"] for g in glyphs])
        self.assertEqual(spell_ids, ["55679", "55680", "55681"])
        
        # Verify categories
        categories_by_name = {g["name"]: g["category"] for g in glyphs}
        self.assertEqual(categories_by_name["Glyph One"], "major")
        self.assertEqual(categories_by_name["Glyph Two"], "major")
        self.assertEqual(categories_by_name["Glyph Three"], "minor")


if __name__ == "__main__":
    unittest.main()

