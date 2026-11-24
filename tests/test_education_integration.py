import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urljoin

from watchers import education_to_graph


ROOT = Path(__file__).resolve().parents[1]


class EducationIntegrationTests(unittest.TestCase):
    def test_grade_mapping_matches_current_activity_destinations(self):
        expected = {
            "k2": {"civic_records", "agenda_viewer"},
            "g35": {"agenda_viewer"},
            "g68": {"news_vs_record"},
            "g912": {"civic_daily"},
            "college": {"open_data"},
            "grad": {"civic_records"},
        }
        actual = {
            grade["id"]: {tool for band, tool, _ in education_to_graph.USES if band == grade["id"]}
            for grade in education_to_graph.GRADE_BANDS
        }
        self.assertEqual(actual, expected)
        page = (ROOT / "education.html").read_text(encoding="utf-8")
        for grade, tools in expected.items():
            panel = page.split(f'id="{grade}"', 1)[1].split("</div>\n    </div>", 1)[0]
            for tool in tools:
                url = next(item["url"] for item in education_to_graph.CIVIC_TOOLS if item["id"] == tool)
                self.assertIn(f'href="site/{url}"', panel)

    def test_loader_marks_current_edges_without_deleting_old_graph_data(self):
        statements = education_to_graph.build_statements()
        merge = next(item for item in statements if "MERGE (g)-[r:USES]" in item["statement"])
        self.assertEqual(merge["parameters"]["revision"], education_to_graph.EDUCATION_MAP_REVISION)
        self.assertNotIn("DELETE", " ".join(item["statement"] for item in statements).upper())
        self.assertEqual(len(merge["parameters"]["rows"]), len(education_to_graph.USES))

    def test_live_query_filters_old_mapping_and_falls_back_when_not_loaded(self):
        with mock.patch.object(education_to_graph, "cypher", return_value={"results": []}) as cypher:
            with mock.patch.object(education_to_graph, "say") as say:
                education_to_graph.ask("g35")
        statement = cypher.call_args.args[0][0]
        self.assertIn("u.education_map_revision=$revision", statement["statement"])
        self.assertEqual(statement["parameters"]["revision"], education_to_graph.EDUCATION_MAP_REVISION)
        self.assertIn("Choose an agenda item", say.call_args.args[0])

    def test_public_links_connect_the_areas(self):
        expected = {
            "education.html": ("site/games/", "site/films.html", "site/music.html", "site/reports.html"),
            "game_studio/index.html": ("../education.html", "../films.html", "../music.html", "../reports.html"),
            "element_lotus_public/films.html": ("../site/education.html", "../site/games/", "music.html", "../site/reports.html"),
            "element_lotus_public/music.html": ("../site/education.html", "../site/games/", "films.html", "../site/reports.html"),
            "element_lotus_public/civic.html": ("../site/education.html", "../site/games/", "films.html", "music.html"),
        }
        for path, urls in expected.items():
            page = (ROOT / path).read_text(encoding="utf-8")
            for url in urls:
                with self.subTest(path=path, url=url):
                    self.assertIn(f'href="{url}"', page)
        for mount in ("/", "/12sgi-king/"):
            self.assertEqual(
                urljoin(f"https://example.test{mount}games/", "../education.html"),
                f"https://example.test{mount}education.html",
            )


if __name__ == "__main__":
    unittest.main()
