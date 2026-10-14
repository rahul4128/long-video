"""Tests for Hindi listenability and source-grounded documentary graphics."""
import json
from pathlib import Path
import tempfile
import unittest

from spoken_hindi_qc import assess_text, assess_scenes
from editing_director import attach_editing, validate_editing


class HindiTests(unittest.TestCase):
    def test_simple_hindi_is_clear(self):
        result=assess_text("क्या आप जानते हैं? इस मंदिर में लोग हर शाम दीपक जलाते हैं।")
        self.assertFalse(result["severe"])
        self.assertFalse(any(f["type"]=="long_spoken_sentence" for f in result["flags"]))

    def test_formal_words_flagged_without_rewriting(self):
        original="अतएव यह समझना आवश्यक है। किंतु सोचिए, यह हुआ कैसे?"
        result=assess_text(original)
        self.assertTrue(any(f["type"]=="written_only_vocabulary" for f in result["flags"]))
        self.assertIn("अतएव",original)

    def test_unexplained_term_flagged_not_auto_substituted(self):
        result=assess_text("लोग प्रदोष पर मंदिर आते हैं।")
        self.assertTrue(any(f["type"]=="religious_term_needs_simple_explanation"
                            for f in result["flags"]))

    def test_extremely_long_sentence_rejected_only_when_strict(self):
        big=" ".join(["यह","बहुत","पुरानी","बात","है"]*12)+"।"
        with tempfile.TemporaryDirectory() as tmp:
            report=assess_scenes([{"scene_number":1,"text":big}],[],
                report_path=Path(tmp)/"q.json",strict=False)
            self.assertEqual(report["status"],"review")
            with self.assertRaises(ValueError):
                assess_scenes([{"scene_number":1,"text":big}],[],
                    report_path=Path(tmp)/"q2.json",strict=True)


def example(style,pattern):
    return {"scene_number":2,"narration_chunk":"यह रहस्य आखिर कैसे खुला?",
            "director":{"entertainmentBeat":pattern},"visualBeats":[
              {"beatIndex":1,"narrationText":"आपने ऐसा क्यों किया?"},
              {"beatIndex":2,"narrationText":"लेकिन इसका जवाब क्या है"},
              {"beatIndex":3,"narrationText":"आखिर यही असली सच है"},
            ],"shots":[
              {"file":"one.jpg","beatIndex":1,"startSeconds":0,"endSeconds":2,
               "shotType":"wide"},
              {"file":"two.jpg","beatIndex":2,"startSeconds":2,"endSeconds":4,
               "shotType":"detail"},
              {"file":"three.jpg","beatIndex":3,"startSeconds":4,"endSeconds":6,
               "shotType":"close_up"},
            ]}


class DocumentaryMotionTests(unittest.TestCase):
    def test_question_style_one_graphic_max_and_narration_unchanged(self):
        s=example("curiosity_reveal","reveal")
        original=[(shot["file"],shot["startSeconds"],shot["endSeconds"]) for shot in s["shots"]]
        with tempfile.TemporaryDirectory() as tmp:
            report=attach_editing([s],[],report_path=Path(tmp)/"e.json",
                context={"seo_metadata":{"long_video_title":"मंदिर का रहस्य"}})
        self.assertEqual(report["selectedStyle"],"curiosity_reveal")
        self.assertLessEqual(sum(bool(x.get("documentaryGraphic") or x.get("editorialLabel"))
                            for x in s["shots"]),1)
        self.assertTrue(all(x.get("editPurpose") for x in s["shots"]))
        self.assertEqual(original,[(x["file"],x["startSeconds"],x["endSeconds"]) for x in s["shots"]])
        validate_editing([s])

    def test_explainer_progress_comes_from_story(self):
        s=example("presenter_explainer","establish")
        with tempfile.TemporaryDirectory() as tmp:
            report=attach_editing([s],[],report_path=Path(tmp)/"e.json",
                context={"seo_metadata":{"long_video_title":"पूजा कैसे करें"}})
        graphics=[x.get("documentaryGraphic") for x in s["shots"] if x.get("documentaryGraphic")]
        self.assertEqual(len(graphics),1)
        self.assertEqual(graphics[0]["kind"],"explainer_step")
        self.assertEqual(graphics[0]["step"],2)
        self.assertEqual(graphics[0]["total"],3)

    def test_reject_excess_cards_and_false_progress(self):
        s=example("presenter_explainer","establish")
        for shot in s["shots"][:2]:
            shot["editTreatment"]="clean";shot["transition"]="cut"
            shot["documentaryGraphic"]={"kind":"explainer_step","label":"जानिए सच","step":6,"total":3}
        s["shots"][2]["editTreatment"]="clean";s["shots"][2]["transition"]="cut"
        with self.assertRaises(ValueError):validate_editing([s])


if __name__=="__main__":
    unittest.main()
