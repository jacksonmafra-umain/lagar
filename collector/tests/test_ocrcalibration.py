import unittest

from lagar import ocrcalibration


class CompareTest(unittest.TestCase):
    def test_identical_text(self):
        self.assertEqual(ocrcalibration.compare("1 § Denna lag gäller.", "1 § Denna lag gäller."), (1.0, 1.0, 1.0))

    def test_misread_words(self):
        recall, precision, similarity = ocrcalibration.compare("12 § 1 st gäller", "12 8 1 st gäller")
        self.assertEqual((recall, precision), (0.8, 0.8))  # "§" read as "8"
        self.assertLess(similarity, 1.0)

    def test_order_does_not_matter_for_words(self):
        self.assertEqual(ocrcalibration.compare("a b c", "c b a")[:2], (1.0, 1.0))

    def test_summary(self):
        rows = [{"word_recall": 0.9, "word_precision": 0.8, "character_similarity": 0.95},
                {"word_recall": 1.0, "word_precision": 1.0, "character_similarity": 1.0}]
        self.assertEqual(ocrcalibration.summary(rows)["word_recall"], {"mean": 0.95, "median": 0.95, "min": 0.9})
        self.assertIsNone(ocrcalibration.summary([])["word_recall"])


if __name__ == "__main__":
    unittest.main()
