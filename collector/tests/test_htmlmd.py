import unittest

from lagar.htmlmd import clean_text, escape_block, markdown_table, to_markdown


class HtmlToMarkdownTests(unittest.TestCase):
    def test_headings_move_down_by_the_offset(self):
        md = to_markdown('<h1>Ref 43</h1><h2 style="margin-left:0cm;">Bakgrund</h2><h6>Djup</h6>', 2)
        self.assertEqual(md, "### Ref 43\n\n#### Bakgrund\n\n###### Djup")

    def test_paragraphs_whitespace_and_invisible_characters(self):
        md = to_markdown("<p>370&nbsp;ha\n  och assistans­ersättning</p><p> </p><p>Nästa</p>")
        self.assertEqual(md, "370 ha och assistansersättning\n\nNästa")

    def test_bold_keeps_spaces_outside_the_markers(self):
        md = to_markdown("<p><strong>Bakgrund&nbsp;</strong>text <i> kursiv </i>.</p>")
        self.assertEqual(md, "**Bakgrund** text *kursiv* .")

    def test_empty_inline_markup_is_dropped(self):
        self.assertEqual(to_markdown("<p>a<strong> </strong>b</p>"), "a b")

    def test_line_breaks_become_hard_breaks(self):
        self.assertEqual(to_markdown("<p>Samma&nbsp;<br>år</p>"), "Samma\\\når")
        self.assertEqual(to_markdown("<p><br>&nbsp;</p>"), "")

    def test_lists_and_tables(self):
        md = to_markdown("<ul><li>a</li><li>b</li></ul><ol><li>x</li><li>y</li></ol>"
                         "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>")
        self.assertEqual(md, "- a\n- b\n\n1. x\n2. y\n\nA | B\n\n1 | 2")

    def test_links_keep_text_only_and_scripts_are_dropped(self):
        md = to_markdown('<p><a href="/api/v1/bilagor/x">bilaga</a><script>alert(1)</script></p>')
        self.assertEqual(md, "bilaga")

    def test_leading_hash_is_escaped(self):
        self.assertEqual(to_markdown("<p># inte rubrik</p>"), "\\# inte rubrik")



class HelperTests(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(clean_text("  a\u00a0\u00adb\n\tc\u200b "), "a b c")

    def test_escape_block(self):
        self.assertEqual((escape_block("# x"), escape_block("x #")), ("\\# x", "x #"))

    def test_markdown_table(self):
        rows = [["A", "", "B"], ["1", "", "2|3", "extra"], ["x"]]
        self.assertEqual(markdown_table(rows),
                         "| A | B | |\n| --- | --- | --- |\n| 1 | 2\\|3 | extra |\n| x | | |")
        self.assertEqual(markdown_table([["", ""]]), "")
        self.assertEqual(markdown_table([]), "")


if __name__ == "__main__":
    unittest.main()
