"""Unit tests for components whose silent failure would corrupt every result.
Run: python3 -m unittest discover -s tests
"""

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ggd.apn import APN, normalized_entropy  # noqa: E402
from ggd.graph import CodeGraph  # noqa: E402
from ggd.labels import apply_file, gold_symbols, parse_patch  # noqa: E402
from ggd.lexical import extract_identifiers, subtokens  # noqa: E402
from ggd.metrics import acc_at_k, hop_distances, recall_at_k  # noqa: E402
from ggd.methods import parse_final  # noqa: E402
from ggd.stats import auroc, holm, mcnemar, paired_bootstrap  # noqa: E402
from ggd.tools import ToolBox  # noqa: E402

PKG = {
    "pkg/__init__.py": "",
    "pkg/core.py": textwrap.dedent('''
        from pkg.util import helper

        class Base:
            def run(self):
                return self.step()

            def step(self):
                return helper(1)

        def top(x):
            b = Base()
            return b.run() + x
        '''),
    "pkg/util.py": textwrap.dedent('''
        def helper(v):
            return v + 1
        '''),
    "tests/test_core.py": "def test_x():\n    assert True\n",
}


def make_repo(d: Path):
    for rel, src in PKG.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)


class TestGraph(unittest.TestCase):
    def test_build(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(Path(d))
            g = CodeGraph.from_repo(d)
        self.assertIn("pkg.core.Base.step", g.nodes)
        self.assertNotIn("tests.test_core.test_x", g.nodes)       # tests excluded
        self.assertIn(("pkg.util.helper", "calls"), g.out["pkg.core.Base.step"])
        self.assertIn(("pkg.core.Base.step", "calls"), g.out["pkg.core.Base.run"])
        self.assertIn(("pkg.util.helper", "imports"), g.out["pkg.core"])
        g.add_containment()
        self.assertIn(("pkg.core.Base.run", "contains"), g.out["pkg.core.Base"])

    def test_official_json(self):
        data = {"directed": True, "multigraph": True, "graph": {},
                "nodes": [{"id": "a.f", "name": "a.f", "text": "def f(): g()"},
                          {"id": "a.g", "name": "a.g", "text": "def g(): pass"}],
                "edges": [{"source": "a.f", "target": "a.g", "type": "calls", "key": 0}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
        g = CodeGraph.from_official_json(f.name)
        self.assertEqual(g.edge_types(), {"calls": 1})
        self.assertEqual(g.nodes["a.f"].kind, "function")


class TestLabels(unittest.TestCase):
    PATCH = textwrap.dedent('''\
        diff --git a/pkg/core.py b/pkg/core.py
        --- a/pkg/core.py
        +++ b/pkg/core.py
        @@ -8,7 +8,10 @@ class Base:
             def step(self):
        -        return helper(1)
        +        return helper(2)
        +
        +    def extra(self):
        +        return 0

         def top(x):
             b = Base()
        ''')

    def test_gold(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(Path(d))
            gold = gold_symbols(self.PATCH, d)
        self.assertEqual(gold["functions"], ["pkg.core.Base.step"])
        self.assertEqual(gold["classes"], ["pkg.core.Base"])          # new method -> its class
        self.assertEqual(gold["new_symbols"], ["pkg.core.Base.extra"])

    def test_apply(self):
        base = PKG["pkg/core.py"].splitlines()
        new, removed, added = apply_file(base, parse_patch(self.PATCH)[0])
        self.assertIn("        return helper(2)", new)
        self.assertNotIn("        return helper(1)", new)
        self.assertEqual(len(new), len(base) + 3)


class TestRanking(unittest.TestCase):
    def test_apn_and_tools(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(Path(d))
            g = CodeGraph.from_repo(d)
        g.add_containment()
        r = APN(g).rank("`helper` returns the wrong value when called from Base.step")
        self.assertIn("pkg.util.helper", r.ranked[:3])
        self.assertTrue(0.0 <= r.uncertainty <= 1.0)
        tb = ToolBox(g)
        self.assertIn("pkg.core.Base.step", tb.get_code_neighbors("pkg.util.helper"))
        self.assertTrue(tb.get_code_neighbors("nope").startswith("ERROR"))
        self.assertEqual(tb.invalid, 1)
        self.assertEqual(parse_final("blah\nFINAL: pkg.util.helper, Base.step, junk", tb),
                         ["pkg.util.helper", "pkg.core.Base.step"])

    def test_entropy(self):
        self.assertAlmostEqual(normalized_entropy([1, 1, 1, 1]), 1.0, places=6)
        self.assertLess(normalized_entropy([10, 0, 0, 0]), 0.01)


class TestLexical(unittest.TestCase):
    def test_tokens(self):
        self.assertEqual(subtokens("getNetrcAuth parse_url"), ["netrc", "auth", "parse", "url"])
        ids = extract_identifiers('Calling `Session.send()` fails\n  File "requests/sessions.py", line 3, in send')
        self.assertIn("Session.send", ids)
        self.assertIn("requests.sessions", ids)


class TestMetricsStats(unittest.TestCase):
    def test_metrics(self):
        self.assertEqual(recall_at_k(["a", "b", "c"], ["c", "z"], 3), 0.5)
        self.assertEqual(acc_at_k(["a", "b"], ["a", "b"], 2), 1.0)
        self.assertIsNone(recall_at_k(["a"], [], 1))

    def test_hops(self):
        g = CodeGraph()
        from ggd.graph import Node
        for n in "abcd":
            g.add_node(Node(n))
        g.add_edge("a", "b", "calls")
        g.add_edge("c", "b", "calls")
        self.assertEqual(hop_distances(g, ["a"]), {"a": 0, "b": 1, "c": 2})

    def test_stats(self):
        a = {str(i): 0.0 for i in range(40)}
        b = {str(i): 1.0 if i < 30 else 0.0 for i in range(40)}
        bs = paired_bootstrap(a, b, n=2000)
        self.assertAlmostEqual(bs["delta"], 0.75)
        self.assertGreater(bs["ci95"][0], 0.5)
        self.assertLess(mcnemar(a, b)["p_exact"], 1e-6)
        self.assertEqual(holm({"x": 0.01, "y": 0.04}), {"x": 0.02, "y": 0.04})
        self.assertEqual(auroc([0.9, 0.8, 0.1], [1, 1, 0]), 1.0)


if __name__ == "__main__":
    unittest.main()
