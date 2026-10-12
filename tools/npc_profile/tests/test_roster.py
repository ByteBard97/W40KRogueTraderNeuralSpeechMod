import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
import roster  # noqa: E402
from roster import NARRATOR  # noqa: E402

ROOT = HERE.parents[3]


def conv(lines, name="Test_dialogue"):
    out = []
    for i, (kind, who, text) in enumerate(lines):
        sp = {"kind": "player"} if who == "PLAYER" else {"kind": "narrator"} if who == NARRATOR else \
            {"kind": "default_speaker"} if who == "??" else {"kind": "unit", "name": who}
        out.append({"kind": kind, "text": text, "text_key": f"k{i}", "speaker": sp})
    return {"name": name, "lines": out}


class Lines(unittest.TestCase):
    def test_numbers_and_targets(self):
        c = conv([("cue", "??", '"Hello." {n}He nods.{/n}'), ("answer", "PLAYER", '"Hi."'), ("cue", "Cassia", '"Well."')])
        ls = roster.conversation_lines(c, {"k0", "k2"})
        self.assertEqual([l["n"] for l in ls], [1, 2, 3])
        self.assertEqual([l["target"] for l in ls], [True, False, False])  # k2 is named, so never a target
        self.assertEqual(ls[0]["text"], '"Hello." He nods.')

    def test_skips_lines_without_text_and_other_kinds(self):
        c = conv([("cue", "??", "Words."), ("sequence", "??", "x")])
        c["lines"].append({"kind": "cue", "text": "", "text_key": "z", "speaker": {"kind": "default_speaker"}})
        self.assertEqual(len(roster.conversation_lines(c, {"k0"})), 1)

    def test_pure_narration(self):
        self.assertTrue(roster.is_pure_narration("Sector: Koronus Expanse"))
        self.assertFalse(roster.is_pure_narration('He says "no".'))


class Chunking(unittest.TestCase):
    def test_only_chunks_with_targets_and_lead_in(self):
        rows = [("cue", "??", f'"line {i}"') for i in range(100)]
        c = conv(rows)
        ls = roster.conversation_lines(c, {f"k{i}" for i in range(90, 100)})
        got = list(roster.chunks(ls, size=40, context=6))
        self.assertEqual(len(got), 1)  # only the last window holds targets
        lead, body = got[0]
        self.assertEqual(body[0]["n"], 81)
        self.assertEqual(len(lead), 6)
        self.assertEqual(lead[-1]["n"], 80)


class Prompt(unittest.TestCase):
    def test_marks_targets_and_lists_known(self):
        c = conv([("cue", "Cassia", '"A."'), ("cue", "??", '"B."')])
        ls = roster.conversation_lines(c, {"k1"})
        known = [{"id": "vir", "name": "Vir", "gender": "male", "species": "human", "role": "machinist"}]
        p = roster.build_prompt("X_dialogue", [], ls, known)
        self.assertIn("#2 [??]", p)
        self.assertIn("[Cassia]", p)
        self.assertNotIn("#1", p)
        self.assertIn("Attribute these line numbers: #2", p)
        self.assertIn("- vir: Vir, male, human, machinist", p)


class Validate(unittest.TestCase):
    def body(self):
        c = conv([("cue", "??", '"Hi." He grins.'), ("cue", "??", "Dust settles."), ("cue", "??", '"Bye."')])
        return roster.conversation_lines(c, {"k0", "k1", "k2"})

    def test_repairs_bad_model_output(self):
        res = {"roster": [{"id": "Falco!", "name": "Falco", "gender": "MALE?", "species": "human", "age": "adult",
                           "role": "trader", "baseline_voice": "smooth", "evidence": ["a", "b", "c", "d"], "confidence": 7},
                          {"id": "falco", "name": "dup"}],
               "lines": [{"n": 1, "speaker": "falco", "delivery": "smirk"}, {"n": 1, "speaker": "other"},
                         {"n": 2, "speaker": "falco"}, {"n": 99, "speaker": "falco"}, {"n": 3, "speaker": "ghost"}]}
        out = roster.validate(res, self.body())
        self.assertEqual([r["id"] for r in out["roster"]], ["falco"])  # id cleaned, duplicate dropped
        r = out["roster"][0]
        self.assertEqual((r["gender"], r["confidence"], len(r["evidence"])), ("unknown", 1.0, 3))
        sp = {l["n"]: l["speaker"] for l in out["lines"]}
        self.assertEqual(sp, {1: "falco", 2: NARRATOR, 3: "unknown"})  # no-quote line forced to narrator, ghost -> unknown

    def test_fills_missing_lines(self):
        out = roster.validate({"roster": [], "lines": []}, self.body())
        self.assertEqual({l["n"]: l["speaker"] for l in out["lines"]}, {1: "unknown", 2: NARRATOR, 3: "unknown"})


class Merge(unittest.TestCase):
    def entry(self, rid, name, gender="male", age="adult", conf=0.8):
        return {"id": rid, "name": name, "gender": gender, "species": "human", "age": age, "role": "trader",
                "baseline_voice": "smooth", "evidence": ["q"], "confidence": conf}

    def test_same_name_across_conversations_is_one_identity(self):
        m = roster.merge_rosters({"A": [self.entry("falco", "Falco", "unknown")], "B": [self.entry("f", "falco", "male")],
                                  "C": [self.entry("x", None)]})
        self.assertIn("falco", m)
        self.assertEqual(m["falco"]["gender"], "male")  # unknown never beats a real value
        self.assertEqual(m["falco"]["conversations"], ["A", "B"])
        self.assertEqual(len(m), 2)  # the unnamed one stays separate


class Attribute(unittest.TestCase):
    def test_end_to_end_with_fake_model_and_narration_skip(self):
        c = conv([("cue", "??", "Sector: Koronus Expanse"),
                  ("cue", "??", '"Who goes there?" The shaking man lowers a lasgun.'),
                  ("answer", "PLAYER", '"A friend."'),
                  ("cue", "??", '"Then welcome," says Vir.')])
        calls = []

        def fake(system, user, schema):
            calls.append(user)
            return {"roster": [{"id": "vir", "name": "Vir", "gender": "male", "species": "human", "age": "adult",
                                "role": "machinist", "baseline_voice": "frightened", "evidence": ["says Vir"], "confidence": 0.9}],
                    "lines": [{"n": 2, "speaker": "vir", "delivery": "stammer"}, {"n": 4, "speaker": "vir", "delivery": ""}]}

        out = roster.attribute(c, {"k0", "k1", "k3"}, fake)
        self.assertEqual(len(calls), 1)
        self.assertEqual({l["n"]: l["speaker"] for l in out["lines"]}, {1: NARRATOR, 2: "vir", 4: "vir"})
        self.assertEqual(out["roster"][0]["name"], "Vir")

    def test_all_narration_makes_no_call(self):
        c = conv([("cue", "??", "Region: Orsellio"), ("cue", "??", "Location: Sanctum")])

        def boom(*a):
            raise AssertionError("model should not be called")

        out = roster.attribute(c, {"k0", "k1"}, boom)
        self.assertTrue(all(l["speaker"] == NARRATOR for l in out["lines"]))


class Gender(unittest.TestCase):
    def test_pronouns_in_narration_only(self):
        self.assertEqual(roster.narration_gender(['The shaking man keeps glancing. "She is lost," he says.', "He lowers his lasgun."]), "male")
        self.assertEqual(roster.narration_gender(['"He did it, his plan," she says. Her eyes narrow.', "She turns."]), "female")
        self.assertEqual(roster.narration_gender(['"He, him, his, man," they said.']), "unknown")  # speech is ignored
        self.assertEqual(roster.narration_gender(["He nods. She nods. He waits. She waits."]), "unknown")  # mixed

    def test_attribute_fills_unknown_gender(self):
        c = conv([("cue", "??", 'The shaking man lowers his lasgun. "Who goes there?"'), ("cue", "??", 'He blinks. "Friend?"')])

        def fake(system, user, schema):
            return {"roster": [{"id": "vir", "name": "Vir", "gender": "unknown", "species": "human", "age": "adult", "role": "x",
                                "baseline_voice": "v", "evidence": [], "confidence": 0.9}],
                    "lines": [{"n": 1, "speaker": "vir", "delivery": '"Who goes there?"'}, {"n": 2, "speaker": "vir", "delivery": "wary"}]}

        out = roster.attribute(c, {"k0", "k1"}, fake)
        self.assertEqual(out["roster"][0]["gender"], "male")
        self.assertEqual([l["delivery"] for l in out["lines"]], ["", "wary"])  # copied quote dropped


class Refine(unittest.TestCase):
    def ent(self, **kw):
        base = {"id": "elder", "name": None, "gender": "unknown", "species": "human", "age": "unknown", "role": "", "baseline_voice": "grating",
                "evidence": ["a"], "confidence": 0.9, "fx": []}
        base.update(kw)
        return base

    def test_later_chunk_adds_name_and_facts(self):
        run = [self.ent()]
        roster.refine_roster(run, [self.ent(name="Leads-Ahead", gender="female", age="old", evidence=["b", "a"], baseline_voice="grating, archaic")])
        r = run[0]
        self.assertEqual((r["name"], r["gender"], r["age"]), ("Leads-Ahead", "female", "old"))
        self.assertEqual(r["evidence"], ["a", "b"])
        self.assertEqual(r["baseline_voice"], "grating, archaic")

    def test_never_overwrites_known_facts(self):
        run = [self.ent(name="Ravor", gender="male")]
        roster.refine_roster(run, [self.ent(name="Someone", gender="female")])
        self.assertEqual((run[0]["name"], run[0]["gender"]), ("Ravor", "male"))

    def test_attribute_refines_across_chunks_and_prunes_unused(self):
        rows = [("cue", "??", f'"line {i}"') for i in range(60)]
        c = conv(rows)
        calls = []

        def fake(system, user, schema):
            calls.append(1)
            first = len(calls) == 1
            ent = lambda i, **kw: {"id": i, "name": None, "gender": "unknown", "species": "human", "age": "unknown", "role": "r",
                                   "baseline_voice": "v", "evidence": [], "confidence": 0.9, "fx": [], **kw}
            ros = [ent("elder")] if first else [ent("elder", name="Leads-Ahead"), ent("ghost")]
            n0 = 1 if first else 41
            return {"roster": ros, "lines": [{"n": n, "speaker": "elder", "delivery": "", "fx": []} for n in range(n0, n0 + 20)]}

        out = roster.attribute(c, {f"k{i}" for i in range(60)}, fake)
        self.assertEqual([r["id"] for r in out["roster"]], ["elder"])  # 'ghost' never speaks, so it is dropped
        self.assertEqual(out["roster"][0]["name"], "Leads-Ahead")


class Confidence(unittest.TestCase):
    def toks(self, pieces):
        return [{"token": p, "logprob": __import__("math").log(prob)} for p, prob in pieces]

    def test_field_probabilities_from_tokens(self):
        from confidence import field_confidence
        t = self.toks([('{"roster":[{"id":"', 1), ("vir", .9), ('","gender":"', 1), ("male", .95), ('","species":"', 1), ("human", .99),
                       ('","age":"', 1), ("unknown", .5), ('","fx":[', 1), ('"machine"', .6), ('"]}],"lines":[{"n":', 1), ("2", 1),
                       (',"speaker":"', 1), ("vir", .7), ('","fx":[', 1), ("]", .8), ("}]}", 1)])
        c = field_confidence(t)
        self.assertAlmostEqual(c["roster"]["vir"]["gender"], .95, 3)
        self.assertAlmostEqual(c["roster"]["vir"]["age"], .5, 3)
        self.assertAlmostEqual(c["roster"]["vir"]["fx"], .6, 3)
        self.assertAlmostEqual(c["lines"]["2"]["speaker"], .7, 3)
        self.assertAlmostEqual(c["lines"]["2"]["fx"], .8, 3)  # empty list: the closing bracket was the choice

    def test_forced_synonym_is_renormalised_over_allowed_values(self):
        from confidence import field_confidence
        import math
        lp = lambda p: math.log(p)
        age = {"token": "old", "logprob": lp(.077), "top_logprobs": [
            {"token": "elder", "logprob": lp(.918)}, {"token": "old", "logprob": lp(.077)}, {"token": "young", "logprob": lp(.002)}, {"token": "adult", "logprob": lp(.001)}]}
        t = self.toks([('{"roster":[{"id":"', 1), ("w", 1), ('","age":"', 1)]) + [age] + self.toks([('"}],"lines":[]}', 1)])
        c = field_confidence(t, {"age": ["child", "young", "adult", "middle", "old", "unknown"]})
        self.assertAlmostEqual(c["roster"]["w"]["age"], .077 / (.077 + .002 + .001), 3)  # 'elder' is not an allowed value
        self.assertAlmostEqual(field_confidence(t)["roster"]["w"]["age"], .077, 3)  # without enums the raw value is kept

    def test_multi_token_value_multiplies(self):
        from confidence import field_confidence
        t = self.toks([('{"roster":[{"id":"', 1), ("x", 1), ('","gender":"', 1), ("fe", .5), ("male", .5), ('"}],"lines":[]}', 1)])
        self.assertAlmostEqual(field_confidence(t)["roster"]["x"]["gender"], .25, 3)


class Audit(unittest.TestCase):
    def res(self, **kw):
        r = {"id": "vir", "name": "Vir", "label": "", "gender": "male", "species": "human", "age": "adult", "role": "", "baseline_voice": "",
             "evidence": [], "confidence": .9, "fx": [], "conf": {"gender": .98, "species": .99, "age": .9}}
        r.update(kw)
        return r

    def test_clean_conversation_passes(self):
        from audit import audit
        a = audit({"roster": [self.res()], "lines": [{"n": 1, "speaker": "vir", "conf": {"speaker": .97}}]})
        self.assertFalse(a["needs_review"])
        self.assertEqual(a["score"], 1.0)

    def test_low_probability_and_rules_flag(self):
        from audit import audit
        a = audit({"roster": [self.res(conf={"gender": .6, "species": .99, "age": .9}), self.res(id="b", name=None, gender="unknown", species="human")],
                   "lines": [{"n": 1, "speaker": "unknown", "conf": {}}, {"n": 2, "speaker": "vir", "conf": {"speaker": .55}}]}, threshold=.8)
        self.assertTrue(a["needs_review"])
        self.assertEqual(a["score"], .55)
        text = " ".join(a["reasons"])
        for want in ("gender=male p=0.60", "gender unknown", "speaker unknown", "line 2"):
            self.assertIn(want, text)

    def test_machine_with_unknown_gender_is_fine_and_threshold_is_tunable(self):
        from audit import audit
        robo = self.res(gender="unknown", species="machine")
        self.assertFalse(audit({"roster": [robo], "lines": []})["needs_review"])
        shaky = {"roster": [self.res(conf={"gender": .85})], "lines": []}
        self.assertFalse(audit(shaky, .8)["needs_review"])
        self.assertTrue(audit(shaky, .9)["needs_review"])

    def test_age_and_species_are_looser_than_gender(self):
        from audit import audit
        mk = lambda **c: {"roster": [self.res(conf={"gender": .98, "species": .99, "age": .9, **c})], "lines": []}
        self.assertFalse(audit(mk(age=.3))["needs_review"])  # 0.3 > 0.8 * 0.3
        self.assertTrue(audit(mk(age=.2))["needs_review"])
        self.assertFalse(audit(mk(species=.65))["needs_review"])  # 0.65 > 0.8 * 0.75
        self.assertTrue(audit(mk(species=.55))["needs_review"])
        self.assertTrue(audit({"roster": [self.res(conf={"gender": .7})], "lines": []})["needs_review"])  # gender stays strict

    def test_validate_carries_conf_and_refine_takes_it_with_the_value(self):
        res = roster.validate({"roster": [{"id": "vir", "name": None, "gender": "unknown", "species": "human"}],
                               "lines": [{"n": 1, "speaker": "vir", "fx": []}],
                               "_conf": {"roster": {"vir": {"gender": .9}}, "lines": {"1": {"speaker": .77}}}},
                              roster.conversation_lines(conv([("cue", "??", '"Hi."')]), {"k0"}))
        self.assertEqual(res["lines"][0]["conf"], {"speaker": .77})
        run = [res["roster"][0]]
        roster.refine_roster(run, [{**run[0], "gender": "female", "conf": {"gender": .93}}])
        self.assertEqual((run[0]["gender"], run[0]["conf"]["gender"]), ("female", .93))


class Known(unittest.TestCase):
    def known(self):
        import known as K
        convs = [{"lines": [{"speaker": {"kind": "unit", "name": n, "gender": g}} for _ in range(c)]} for n, g, c in [
            ("Heinrix", "Male", 30), ("Master Helmsman Ravor", "Male", 25), ('Aggressive "Kibellah"', "Female", 3), ("Kibellah", "Female", 40),
            ("Lucky Jaspar", "Female", 1), ("Juvenna von Valancius", "Female", 30), ("Theodora", "Female", 30), ("Theodora Ward", "Male", 2)]]
        return K, K.build_known(convs, {"Heinrix", "Kibellah", "Theodora"})

    def ent(self, **kw):
        return {"name": None, "label": "", "gender": "unknown", **kw}

    def test_matches_name_to_longer_known_name(self):
        K, kn = self.known()
        self.assertEqual(K.match(self.ent(name="Ravor", gender="male"), kn)["speaker"], "Master Helmsman Ravor")
        m = K.match(self.ent(name=None, label="Interrogator Heinrix"), kn)  # name leaked into label
        self.assertEqual((m["speaker"], m["has_bank"]), ("Heinrix", True))
        self.assertEqual(K.match(self.ent(name="Juvenna"), kn)["speaker"], "Juvenna von Valancius")

    def test_longer_character_name_matches_shorter_known_name(self):
        K, kn = self.known()
        self.assertEqual(K.match(self.ent(name="Theodora von Valancius", gender="female"), kn)["speaker"], "Theodora")
        self.assertIsNone(K.match(self.ent(name="Juvenna Ward"), kn))  # shares only part of each name: not a match

    def test_variants_collapse_to_the_established_one(self):
        K, kn = self.known()
        m = K.match(self.ent(name="Kibellah"), kn)
        self.assertEqual(m["speaker"], "Kibellah")  # the 40-line one, not 'Aggressive "Kibellah"'

    def test_generic_labels_and_unknown_names_do_not_match(self):
        K, kn = self.known()
        self.assertIsNone(K.match(self.ent(name=None, label="Pirate Vendor"), kn))
        self.assertIsNone(K.match(self.ent(name="Vir"), kn))
        self.assertIsNone(K.match(self.ent(name=None, label="Tech-Priest"), kn))
        import known as K2
        kn2 = K2.build_known([{"lines": [{"speaker": {"kind": "unit", "name": "Tech-Priest Androveta-Phi", "gender": "Male"}}] * 30}], set())
        self.assertIsNone(K2.match(self.ent(name=None, label="Tech-Priest"), kn2))  # a generic title must not pick out one named person
        self.assertEqual(K2.match(self.ent(name="Androveta-Phi"), kn2)["speaker"], "Tech-Priest Androveta-Phi")

    def test_gender_veto_only_for_established_characters(self):
        K, kn = self.known()
        self.assertIsNone(K.match(self.ent(name="Heinrix", gender="female"), kn))  # 30 lines say male
        m = K.match(self.ent(name="Jaspar", gender="male"), kn)  # 1 line tagged female: trust the text, warn
        self.assertEqual(m["speaker"], "Lucky Jaspar")
        self.assertIn("only 1 line", m["warning"])

    def test_ambiguous_names_are_reported(self):
        K, kn = self.known()
        m = K.match(self.ent(name="Theodora"), kn)
        self.assertEqual(m["speaker"], "Theodora")  # exact token set wins; the other differs, so it is listed
        self.assertEqual(m.get("ambiguous_with"), ["Theodora Ward"])


class Triage(unittest.TestCase):
    def test_tiers(self):
        import triage
        convs = [conv([("cue", "??", "Sector: X")], "narr"), conv([("cue", "??", '"Hi."')], "speech"), conv([("cue", "Cassia", '"Hi."')], "named")]
        t = triage.tiers(convs, {"k0"})
        self.assertEqual((t["tier0"], t["tier1"]), (["narr"], ["speech"]))  # 'named' has no unnamed targets: neither tier

    def test_escalate_worst_first(self):
        import triage
        rows = [{"conversation": n, "audit": {"needs_review": nr, "score": s}} for n, nr, s in [("a", True, .7), ("b", False, 1.0), ("c", True, .2)]]
        self.assertEqual(triage.escalate(rows), ["c", "a"])
        self.assertEqual(triage.escalate(rows, .5), ["c"])


class Compare(unittest.TestCase):
    def res(self, gender="male", age="adult", speaker="vir", fx=None, key="k1"):
        return {"conversation": "X", "roster": [{"id": "vir", "name": "Vir", "label": "", "gender": gender, "species": "human", "age": age, "fx": fx or []}],
                "lines": [{"key": key, "speaker": speaker}]}

    def test_agreement_and_unknown_are_not_conflicts(self):
        import compare
        self.assertEqual(compare.diff(self.res(), self.res()), [])
        self.assertEqual(compare.diff(self.res(age="unknown"), self.res(age="old")), [])

    def test_real_conflicts_reported(self):
        import compare
        d = compare.diff(self.res(), self.res(gender="female", fx=["machine"]))
        self.assertTrue(any("gender male vs female" in x for x in d))
        self.assertTrue(any("fx [] vs ['machine']" in x for x in d))

    def test_line_speaker_difference_counts_across_different_ids(self):
        import compare
        b = self.res()
        b["roster"][0]["id"] = "other"
        b["roster"][0]["name"] = "Falco"
        b["lines"][0]["speaker"] = "other"
        d = compare.diff(self.res(), b)
        self.assertTrue(any("only in" in x for x in d))
        self.assertTrue(any("1 line(s)" in x for x in d))


class Fx(unittest.TestCase):
    def test_clean_fx(self):
        self.assertEqual(roster.clean_fx(["vox_channel", "helmet"]), ["helmet", "vox_channel"])  # fixed order, not the model's
        self.assertEqual(roster.clean_fx("machine"), ["machine"])  # bare string accepted
        self.assertEqual(roster.clean_fx(["dragon", "none", "machine"]), ["machine"])
        self.assertEqual(roster.clean_fx(["machine", "monstrous", "ethereal"]), ["machine", "monstrous"])  # capped at two
        self.assertEqual(roster.clean_fx(None), [])

    def test_validate_cleans_roster_and_lines(self):
        c = conv([("cue", "??", '"Hi." The terminal hisses.'), ("cue", "??", '"Bye."')])
        body = roster.conversation_lines(c, {"k0", "k1"})
        res = {"roster": [{"id": "t", "name": None, "fx": ["robot-voice"]}, {"id": "u", "name": None, "fx": ["machine"]}],
               "lines": [{"n": 1, "speaker": "t", "fx": ["dragon"]}, {"n": 2, "speaker": "u", "fx": ["vox_channel", "machine"]}]}
        out = roster.validate(res, body)
        self.assertEqual([r["fx"] for r in out["roster"]], [[], ["machine"]])
        self.assertEqual([l["fx"] for l in out["lines"]], [[], ["machine", "vox_channel"]])

    def test_narration_never_gets_fx(self):
        c = conv([("cue", "??", "The vox hums.")])
        out = roster.validate({"roster": [], "lines": [{"n": 1, "speaker": "x", "fx": ["machine"]}]}, roster.conversation_lines(c, {"k0"}))
        self.assertEqual((out["lines"][0]["speaker"], out["lines"][0]["fx"]), (NARRATOR, []))

    def test_merge_fx_needs_majority_per_category(self):
        e = lambda fx: {"id": "a", "name": "Jae", "gender": "male", "species": "human", "age": "adult", "role": "", "baseline_voice": "", "evidence": [], "confidence": 1, "fx": fx}
        m = roster.merge_rosters({"A": [e(["helmet", "vox_channel"])], "B": [e(["helmet"])], "C": [e([])]})
        self.assertEqual(m["jae"]["fx"], ["helmet"])  # helmet in 2/3, vox_channel in 1/3
        m = roster.merge_rosters({"A": [e(["helmet"])], "B": [e([])]})
        self.assertEqual(m["jae"]["fx"], [])

    def test_prompt_lists_every_category_and_schema_matches(self):
        for k in roster.FX_NAMES:
            self.assertIn(k, roster.SYSTEM)
        sch = roster.SCHEMA["properties"]["roster"]["items"]["properties"]["fx"]
        self.assertEqual((sch["items"]["enum"], sch["maxItems"]), (roster.FX_NAMES, 2))


class RealData(unittest.TestCase):
    def test_real_conversation_builds_a_prompt(self):
        path = ROOT / "data/conversations.enGB.json"
        if not path.exists():
            self.skipTest("no game data")
        convs = {c["name"]: c for c in json.loads(path.read_text(encoding="utf-8"))}
        jobs = {json.loads(l)["guid"] for l in (ROOT / "data/render/jobs.jsonl").read_text().splitlines() if '"default_speaker"' in l}
        c = convs["FalcoAliveOutcome_dialogue"]
        ls = roster.conversation_lines(c, jobs)
        got = list(roster.chunks(ls))
        self.assertTrue(got)
        prompt = roster.build_prompt(c["name"], *got[0])
        self.assertIn("Falco", prompt)
        self.assertLess(len(prompt), 12000)
        json.dumps(roster.SCHEMA)


if __name__ == "__main__":
    unittest.main()
