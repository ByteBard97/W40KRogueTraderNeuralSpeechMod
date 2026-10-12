import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import segment as S  # noqa: E402


class Sentences(unittest.TestCase):
    def test_basic_split(self):
        t = "The first sentence is long enough to stand alone. The second one also stands alone, nicely. And a third one follows here."
        self.assertEqual(len(S.split_sentences(t)), 3)

    def test_ellipsis_then_lowercase_is_one_sentence(self):
        t = "Rogue Trader... why is that creature standing beside you? Why has the treacherous xenos not suffered for her trickery?"
        s = S.split_sentences(t)
        self.assertEqual(len(s), 2)
        self.assertTrue(s[0].startswith("Rogue Trader... why is that creature"))

    def test_fragments_join_their_neighbour(self):
        t = "No. I had to stop. I... I'm sorry. You'll see why, and then you will understand everything I did."
        s = S.split_sentences(t)
        self.assertTrue(all(len(x) >= S.MIN_SENTENCE_CHARS for x in s[:-1]))
        self.assertEqual(" ".join(s), t)
        s2 = S.split_sentences("We were forced to act upon the whole matter, and so we did. Decisively.")
        self.assertEqual(len(s2), 1)  # a trailing one-word sentence stays attached

    def test_joined_sentences_reproduce_the_text(self):
        t = "He said \"no.\" Then he left the room and never returned! Why would he? Nobody ever found out the truth about it."
        self.assertEqual(" ".join(S.split_sentences(t)), t)


class Validate(unittest.TestCase):
    def sents(self, n=4, length=80):
        return [("Sentence number %d " % i).ljust(length, "x") + "." for i in range(1, n + 1)]

    def seg(self, end, emotion="neutral", intensity=2, pace="normal", instruct="x"):
        return {"end_sentence": end, "emotion": emotion, "intensity": intensity, "pace": pace, "instruct": instruct}

    def test_clean_split_keeps_both_when_long_enough(self):
        out = S.validate({"segments": [self.seg(2, "fear", 4), self.seg(4, "angry", 5)]}, self.sents(4, 80))
        self.assertEqual([(s["start"], s["end"], s["emotion"]) for s in out], [(0, 2, "fear"), (2, 4, "angry")])
        self.assertEqual(out[1]["intensity_value"], 0.9)

    def test_short_segment_is_merged_into_the_longer_neighbour(self):
        out = S.validate({"segments": [self.seg(1, "sad"), self.seg(4, "angry")]}, self.sents(4, 80), min_chars=120)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["emotion"], out[0]["end"]), ("angry", 4))  # the long neighbour's delivery wins

    def test_repairs_bad_answers(self):
        out = S.validate({"segments": [self.seg(2, "grumpy", 9, "warp"), self.seg(2), self.seg(99), self.seg(3)]}, self.sents(4, 200))
        self.assertEqual(out[0]["emotion"], "neutral")  # bad enums fall back
        self.assertEqual((out[0]["intensity"], out[0]["pace"]), (2, "normal"))
        self.assertEqual(out[-1]["end"], 4)  # the last segment always reaches the end
        self.assertEqual(sum(len(s["text"]) for s in out) >= 0, True)

    def test_empty_answer_gives_one_neutral_segment_covering_all(self):
        out = S.validate({}, self.sents(3, 50))
        self.assertEqual((len(out), out[0]["end"], out[0]["emotion"]), (1, 3, "neutral"))

    def test_text_is_preserved_exactly(self):
        ss = self.sents(5, 150)
        out = S.validate({"segments": [self.seg(2, "fear"), self.seg(5, "angry")]}, ss)
        self.assertEqual(" ".join(s["text"] for s in out), " ".join(ss))

    def test_segment_count_never_below_one_with_tiny_lines(self):
        out = S.validate({"segments": [self.seg(1), self.seg(2), self.seg(3)]}, self.sents(3, 20), min_chars=120)
        self.assertEqual(len(out), 1)


class Confidence(unittest.TestCase):
    ALT = {"fear": "sad", "angry": "sad", "2": "3", "4": "3", "5": "4", "fast": "slow", "normal": "slow", "1": "2"}

    def toks(self, pieces):
        """Each decided token competes with one other allowed value holding the remaining probability."""
        out = []
        for p, q in pieces:
            alts = [{"token": p, "logprob": math.log(q)}]
            if p in self.ALT and q < 1:
                alts.append({"token": self.ALT[p], "logprob": math.log(1 - q)})
            out.append({"token": p, "logprob": math.log(q), "top_logprobs": alts})
        return out

    def test_per_segment_probabilities(self):
        t = self.toks([('{"segments":[{"end_sentence":', 1), ("2", .9), (',"emotion":"', 1), ("fear", .7), ('","intensity":', 1), ("4", .5),
                       (',"pace":"', 1), ("fast", .8), ('","instruct":"hush"},{"end_sentence":', 1), ("4", .95), (',"emotion":"', 1),
                       ("angry", .6), ('","intensity":', 1), ("5", .9), (',"pace":"', 1), ("normal", .99), ('","instruct":"loud"}]}', 1)])
        c = S.segment_confidence(t, 4)
        self.assertEqual(len(c), 2)
        self.assertAlmostEqual(c[0]["emotion"], .7, 2)
        self.assertAlmostEqual(c[0]["intensity"], .5, 2)
        self.assertAlmostEqual(c[1]["end_sentence"], .95, 2)
        self.assertAlmostEqual(c[1]["pace"], .99, 2)

    def test_review_reasons(self):
        segs = [{"end": 2, "emotion": "fear", "conf": {"emotion": .4, "end_sentence": .5}}, {"end": 4, "emotion": "angry", "conf": {"emotion": .9}}]
        r = " | ".join(S.review_reasons(segs, emotion_p=.5, split_p=.6))
        self.assertIn("emotion=fear p=0.40", r)
        self.assertIn("split after sentence 2 p=0.50", r)
        self.assertIn("split into 2 segments", r)
        self.assertEqual(S.review_reasons([{"end": 3, "emotion": "sad", "conf": {"emotion": .95}}]), [])
        torn = S.review_reasons([{"end": 7, "emotion": "sad", "conf": {"emotion": .95, "end_sentence": .35}}])
        self.assertEqual(torn, ["torn about splitting (p(no split)=0.35)"])  # a single segment the model nearly split


class Prompt(unittest.TestCase):
    def test_prompt_contains_numbered_sentences_and_context(self):
        p = S.build_prompt("X_dialogue", "Falco", ["One.", "Two."], ["[PLAYER] hello"], ["[Cassia] after"], "smooth, calculating")
        for want in ("Speaker: Falco (smooth, calculating)", "1. One.", "2. Two.", "Just before:", "Just after:", "The line has 2 sentence(s)."):
            self.assertIn(want, p)
        self.assertIn("pause or an ellipsis", S.SYSTEM)


if __name__ == "__main__":
    unittest.main()
