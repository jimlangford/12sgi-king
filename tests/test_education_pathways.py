import unittest
from watchers.education_pathways import pathway
from watchers.education_to_graph import GRADE_BANDS, USES

class TestEducationPathways(unittest.TestCase):
    def test_all_bands(self):
        for band in GRADE_BANDS:
            p = pathway(band["id"])
            self.assertEqual(p["grade"], band["id"])
            self.assertEqual(len(p["civic"]), sum(g == band["id"] for g, _, _ in USES))
            self.assertEqual(p["game"]["classification"], "simulation_not_evidence")
            self.assertEqual(p["film"]["assets"], [])
            self.assertEqual(p["publishing"]["status"], "not_staged")
            self.assertEqual(p["publishing"]["account_scope"], "education")

    def test_unknown_grade(self):
        with self.assertRaises(ValueError):
            pathway("unknown")

if __name__ == "__main__":
    unittest.main()
