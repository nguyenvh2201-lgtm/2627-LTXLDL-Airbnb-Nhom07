"""Kiểm tra contract mixed và luồng LLM → KPI bằng dữ liệu giả lập.

Không gọi API thật. Nhãn trong test không phải bộ nhãn người để nộp bài.
"""

from contextlib import redirect_stdout
from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

import pandas as pd

from src import kpi, llm, qa


SNAPSHOT = "2026-06-15"
ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, rows):
    """Ghi fixture trong thư mục tạm, không chạm dữ liệu của dự án."""
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prediction(label, aspects=None):
    """Tạo dự đoán hợp lệ; None biểu diễn review chưa đủ căn cứ."""
    result = {
        "sentiment": label,
        "aspects": aspects or [],
        "language": "en",
        "status": "ok",
        "error": None,
    }
    if label is None:
        result["status"] = "needs_review"
        result["error"] = "Factual statement only"
    return result


def api_response(result):
    """Bọc dự đoán theo định dạng Chat Completions đang dùng."""
    return {
        "model": "synthetic-model",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "choices": [{
            "finish_reason": "stop",
            "message": {"content": json.dumps(result)},
        }],
    }


class LLMKPIContractTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.output = self.folder / "mixed.jsonl"
        self.config = llm.load_config("luna")
        self.config["api_key_env"] = "SYNTHETIC_LLM_TEST_KEY"
        self.config["interval_seconds"] = 0
        self.args = SimpleNamespace(skip_llm=False, max_new_requests=None)

    def run_batch(self, rows, responses):
        """Chạy runner thật với API giả; trả exit code và số lần gọi."""
        signature = llm.build_run_signature(self.config, rows)
        with patch.dict("os.environ", {"SYNTHETIC_LLM_TEST_KEY": "test-only"}):
            with patch.object(llm, "request_review", side_effect=responses) as request:
                with patch.object(llm.time, "sleep"), redirect_stdout(StringIO()):
                    exit_code = llm.run(rows, self.config, self.output, signature, self.args)
        return exit_code, request.call_count

    def sample_rows(self, count):
        """Tạo ID có số 0 đầu để kiểm tra không bị đổi kiểu khi nối bảng."""
        rows = []
        for index in range(count):
            listing = "0001"
            if index % 2:
                listing = "0002"
            rows.append({
                "snapshot_date": SNAPSHOT,
                "review_id": f"{index:05d}",
                "listing_id": listing,
                "text": "Synthetic review",
                "split": "dev",
            })
        return rows

    def generate_mixed_batch(self):
        """30 review dùng được + 1 needs_review + 1 trượt QA."""
        rows = self.sample_rows(32)
        responses = []
        for index in range(30):
            label = llm.LABELS[index // 10]
            responses.append(api_response(prediction(
                label, [{"aspect": "noise", "polarity": label}]
            )))
        responses.append(api_response(prediction(None)))
        rows[-1]["text_valid"] = "false"
        exit_code, calls = self.run_batch(rows, responses)
        self.assertEqual(exit_code, 1)  # Một review trượt QA vẫn được ghi là error.
        self.assertEqual(calls, 31)
        return rows

    def current_listings(self):
        return pd.DataFrame([
            {"snapshot_date": SNAPSHOT, "listing_id": "0001", "neighbourhood_cleansed": "A"},
            {"snapshot_date": SNAPSHOT, "listing_id": "0002", "neighbourhood_cleansed": "B"},
        ])

    def test_all_three_labels_match_kpi_for_sentiment_and_aspects(self):
        self.assertEqual(llm.LABELS, kpi.LLM_LABELS)
        for label in ("positive", "mixed", "negative"):
            with self.subTest(label=label):
                result = prediction(label, [{"aspect": "host", "polarity": label}])
                self.assertEqual(llm.validate(result), result)

    def test_real_duplicate_amenities_response_becomes_one_mixed_aspect(self):
        result = prediction("mixed", [
            {"aspect": "location", "polarity": "positive"},
            {"aspect": "host", "polarity": "positive"},
            {"aspect": "cleanliness", "polarity": "positive"},
            {"aspect": "amenities", "polarity": "positive"},
            {"aspect": "amenities", "polarity": "negative"},
        ])
        original = deepcopy(result)
        normalized = llm.normalize_aspects(result)
        expected = deepcopy(original)
        expected["aspects"] = original["aspects"][:3] + [
            {"aspect": "amenities", "polarity": "mixed"},
        ]
        self.assertEqual(normalized, expected)
        self.assertEqual(llm.parse_response(api_response(original)), expected)
        self.assertEqual(result, original)

    def test_repeated_aspects_merge_all_polarity_combinations(self):
        for first in llm.LABELS:
            for second in llm.LABELS:
                for third in llm.LABELS:
                    with self.subTest(labels=(first, second, third)):
                        aspects = []
                        for label in (first, second, third):
                            aspects.append({"aspect": "amenities", "polarity": label})
                        expected = "mixed"
                        if first == second == third:
                            expected = first
                        normalized = llm.parse_response(api_response(prediction("mixed", aspects)))
                        self.assertEqual(normalized["aspects"], [
                            {"aspect": "amenities", "polarity": expected},
                        ])

    def test_aspect_normalization_preserves_valid_predictions(self):
        predictions = [prediction(None)]
        for label in llm.LABELS:
            predictions.append(prediction(label))
            predictions.append(prediction(label, [
                {"aspect": "host", "polarity": label},
                {"aspect": "location", "polarity": label},
            ]))
        for result in predictions:
            with self.subTest(result=result):
                self.assertEqual(llm.parse_response(api_response(result)), result)

    def test_aspect_normalization_rejects_malformed_predictions(self):
        invalid = [None, [], {}, prediction("neutral")]
        for aspect in (
            None,
            "amenities",
            {"aspect": "amenities"},
            {"aspect": "amenities", "polarity": "neutral"},
            {"aspect": "unknown", "polarity": "positive"},
            {"aspect": "amenities", "polarity": "positive", "extra": 1},
        ):
            invalid.append(prediction("mixed", [
                {"aspect": "amenities", "polarity": "positive"},
                aspect,
            ]))
        for aspects in (None, {}, "amenities"):
            result = prediction("mixed")
            result["aspects"] = aspects
            invalid.append(result)
        for field, value in (("language", ""), ("status", "error"), ("extra", 1)):
            result = prediction("mixed", [
                {"aspect": "amenities", "polarity": "positive"},
                {"aspect": "amenities", "polarity": "negative"},
            ])
            result[field] = value
            invalid.append(result)
        invalid.append(prediction(None, [
            {"aspect": "amenities", "polarity": "positive"},
        ]))
        for result in invalid:
            with self.subTest(result=result):
                with self.assertRaises(ValueError):
                    llm.parse_response(api_response(result))

    def test_incomplete_response_is_rejected_before_aspect_normalization(self):
        for reason in ("length", "content_filter", None):
            with self.subTest(reason=reason):
                response = api_response(prediction("mixed", [
                    {"aspect": "amenities", "polarity": "positive"},
                    {"aspect": "amenities", "polarity": "negative"},
                ]))
                response["choices"][0]["finish_reason"] = reason
                with self.assertRaisesRegex(ValueError, "chưa hoàn tất"):
                    llm.parse_response(response)

    def test_resume_repairs_duplicate_aspect_response_and_preserves_four_cached_rows(self):
        rows = self.sample_rows(5)
        duplicate = api_response(prediction("mixed", [
            {"aspect": "amenities", "polarity": "positive"},
            {"aspect": "amenities", "polarity": "negative"},
        ]))
        responses = []
        for _ in range(4):
            responses.append(api_response(prediction("positive")))
        responses.append(duplicate)

        # Tạo checkpoint bằng cách xử lý cũ, có bốn ok và một error.
        with patch.object(llm, "normalize_aspects", side_effect=llm.validate):
            exit_code, calls = self.run_batch(rows, responses)
        self.assertEqual((exit_code, calls), (1, 5))
        before = []
        for line in self.output.read_text(encoding="utf-8").splitlines():
            before.append(json.loads(line))
        self.assertEqual(before[-1]["error"], "ValueError: Khía cạnh bị lặp")

        self.args.max_new_requests = 1
        exit_code, calls = self.run_batch(rows, [duplicate])
        self.assertEqual((exit_code, calls), (0, 1))
        after = []
        for line in self.output.read_text(encoding="utf-8").splitlines():
            after.append(json.loads(line))
        self.assertEqual(after[:4], before[:4])
        self.assertEqual(after[-1]["aspects"], [
            {"aspect": "amenities", "polarity": "mixed"},
        ])
        self.assertEqual(after[-1]["status"], "ok")

        _, tables = kpi.build_llm_outputs(
            str(self.output), [SNAPSHOT], self.current_listings(), kpi.MIN_N_SHARE
        )
        aspect = tables["kpi_llm_aspect.csv"].iloc[0]
        self.assertEqual(aspect["aspect"], "amenities")
        self.assertEqual(aspect["n_aspect_mentions"], 1)

        saved_bytes = self.output.read_bytes()
        self.args.skip_llm = True
        self.assertEqual(self.run_batch(rows, []), (0, 0))
        self.assertEqual(self.output.read_bytes(), saved_bytes)

    def test_checkpoint_with_duplicate_aspects_is_still_rejected(self):
        rows = self.sample_rows(1)
        self.assertEqual(self.run_batch(rows, [api_response(prediction("positive"))]), (0, 1))
        record = json.loads(self.output.read_text(encoding="utf-8"))
        record["aspects"] = [
            {"aspect": "amenities", "polarity": "positive"},
            {"aspect": "amenities", "polarity": "negative"},
        ]
        llm.write_jsonl(self.output, [record])
        saved_bytes = self.output.read_bytes()
        self.args.skip_llm = True
        with self.assertRaisesRegex(ValueError, "Khía cạnh bị lặp"):
            self.run_batch(rows, [])
        self.assertEqual(self.output.read_bytes(), saved_bytes)

    def test_legacy_neutral_rejected_without_converting_to_mixed(self):
        invalid_predictions = [
            prediction("neutral"),
            prediction("positive", [{"aspect": "host", "polarity": "neutral"}]),
        ]
        for result in invalid_predictions:
            with self.subTest(result=result):
                with self.assertRaises(ValueError):
                    llm.parse_response(api_response(result))
        rows = self.sample_rows(1)
        exit_code, calls = self.run_batch(rows, [api_response(prediction("neutral"))])
        self.assertEqual((exit_code, calls), (1, 1))
        record = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "error")
        self.assertIsNone(record["sentiment"])

    def test_mixed_without_aspects_and_factual_needs_review_are_distinct(self):
        self.assertEqual(llm.validate(prediction("mixed"))["sentiment"], "mixed")
        self.assertIsNone(llm.validate(prediction(None))["sentiment"])
        self.assertEqual(llm.baseline("Great but dirty"), "mixed")
        self.assertEqual(llm.baseline("Stayed two nights"), "unclassified")

    def test_both_profiles_use_shared_city_config_and_accept_json_override(self):
        overrides = self.folder / "overrides.json"
        overrides.write_text('{"interval_seconds": 7}', encoding="utf-8")
        for profile in ("luna", "argon"):
            with self.subTest(profile=profile):
                defaults = llm.load_config(profile)
                shared = llm.load_config(profile, ROOT / "configs" / "city.yaml")
                external = llm.load_config(profile, overrides)
                self.assertEqual(defaults, shared)
                self.assertEqual(defaults["prompt_version"], "tv4-simple-v3-mixed")
                self.assertEqual(external, dict(shared, interval_seconds=7))

    def test_request_sends_mixed_prompt_for_both_models(self):
        for profile in ("luna", "argon"):
            with self.subTest(profile=profile):
                config = llm.load_config(profile)
                with patch.object(llm.requests, "post") as post:
                    post.return_value.json.return_value = api_response(prediction("mixed"))
                    llm.request_review("Review data", config, "test-only")
                payload = post.call_args.kwargs["json"]
                self.assertEqual(payload["model"], config["model"])
                self.assertEqual(payload["messages"][0]["content"], llm.PROMPT)
                self.assertIn("mixed: substantial praise AND criticism", llm.PROMPT)
                self.assertNotIn("neutral", llm.PROMPT)

    def test_old_checkpoint_is_rejected_without_api_or_overwrite(self):
        rows = self.sample_rows(1)
        old_config = deepcopy(self.config)
        old_config["prompt_version"] = "tv4-simple-v2"
        old_prompt = llm.PROMPT.replace("mixed", "neutral").replace(
            "Do not invent facts or an unsupported sentiment.",
            "Do not invent facts or a neutral sentiment.",
        )
        with patch.object(llm, "PROMPT", old_prompt):
            old_signature = llm.build_run_signature(old_config, rows)
        old_record = dict(rows[0])
        old_record.update(prediction("neutral"))
        old_record.update(run_signature=old_signature, prompt_version=old_config["prompt_version"])
        llm.write_jsonl(self.output, [old_record])
        original_bytes = self.output.read_bytes()
        signature = llm.build_run_signature(self.config, rows)
        self.assertNotEqual(old_signature, signature)
        for skip in (False, True):
            with self.subTest(skip_llm=skip):
                self.args.skip_llm = skip
                with patch.object(llm, "request_review") as request:
                    with self.assertRaisesRegex(ValueError, "khác model/prompt"):
                        llm.run(rows, self.config, self.output, signature, self.args)
                request.assert_not_called()
                self.assertEqual(self.output.read_bytes(), original_bytes)

    def test_runner_jsonl_mixed_counts_in_kpi_denominator(self):
        self.generate_mixed_batch()
        checks, tables = kpi.build_llm_outputs(
            str(self.output), [SNAPSHOT], self.current_listings(), kpi.MIN_N_SHARE
        )
        self.assertTrue(checks["status"].eq("PASS").all())
        snapshot = tables["kpi_llm_snapshot.csv"].iloc[0]
        self.assertEqual(snapshot["n_llm_sample"], 32)
        self.assertEqual(snapshot["n_llm_usable"], 30)
        self.assertAlmostEqual(snapshot["llm_parse_coverage"], 30 / 32)
        self.assertAlmostEqual(snapshot["llm_positive_share"], 10 / 30)
        self.assertAlmostEqual(snapshot["llm_negative_share"], 10 / 30)
        aspect = tables["kpi_llm_aspect.csv"].iloc[0]
        self.assertEqual(aspect["n_aspect_mentions"], 30)
        self.assertAlmostEqual(aspect["aspect_negative_share"], 10 / 30)
        areas = tables["kpi_llm_area.csv"]
        self.assertEqual(set(areas["neighbourhood_cleansed"]), {"A", "B"})
        self.assertEqual(int(areas["n_llm_usable"].sum()), 30)
        self.assertTrue(areas["llm_negative_share"].isna().all())

    def test_under_30_usable_reviews_keeps_shares_blank(self):
        self.generate_mixed_batch()
        records = []
        for line in self.output.read_text(encoding="utf-8").splitlines()[:29]:
            records.append(json.loads(line))
        llm.write_jsonl(self.output, records)
        _, tables = kpi.build_llm_outputs(
            str(self.output), [SNAPSHOT], self.current_listings(), kpi.MIN_N_SHARE
        )
        snapshot = tables["kpi_llm_snapshot.csv"].iloc[0]
        self.assertEqual(snapshot["n_llm_usable"], 29)
        self.assertTrue(pd.isna(snapshot["llm_negative_share"]))
        self.assertTrue(pd.isna(snapshot["llm_positive_share"]))
        self.assertTrue(pd.isna(tables["kpi_llm_aspect.csv"].iloc[0]["aspect_negative_share"]))

    def test_kpi_warns_and_excludes_legacy_neutral(self):
        record = dict(self.sample_rows(1)[0])
        record.update(prediction("neutral"))
        llm.write_jsonl(self.output, [record])
        frame = kpi.read_llm(str(self.output), [SNAPSHOT])
        self.assertEqual(kpi.llm_metrics(frame, 30)["n_llm_usable"], 0)
        checks = kpi.llm_checks(frame, self.current_listings()).set_index("check")
        self.assertEqual(checks.loc["llm_ok_sentiment_in_labels", "status"], "WARN")
        self.assertEqual(json.loads(self.output.read_text())["sentiment"], "neutral")

    def test_kpi_rejects_duplicate_review_keys(self):
        record = dict(self.sample_rows(1)[0])
        record.update(prediction("mixed"))
        llm.write_jsonl(self.output, [record, record])
        with self.assertRaisesRegex(ValueError, "trùng"):
            kpi.read_llm(str(self.output), [SNAPSHOT])

    def test_kpi_invalid_json_reports_line_number(self):
        self.output.write_text("\n{invalid json}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "dòng 2"):
            kpi.read_llm(str(self.output), [SNAPSHOT])

    def test_kpi_rejects_jsonl_for_a_different_snapshot(self):
        review = self.sample_rows(1)[0]
        llm.write_jsonl(self.output, [dict(review, **prediction("mixed"))])
        with self.assertRaisesRegex(ValueError, "không có review cho các mốc KPI"):
            kpi.read_llm(self.output, ["2025-11-11"])

    def test_full_kpi_run_produces_eight_tables_and_passes_checks(self):
        self.generate_mixed_batch()
        input_dir = self.folder / "tv2"
        input_dir.mkdir()
        listings = []
        calendars = []
        for snapshot, prices in (("2026-03-19", (80, 180)), (SNAPSHOT, (100, 200))):
            calendar_days = []
            for index, price in enumerate(prices):
                listing = f"{index + 1:04d}"
                room_type = "Entire home/apt"
                rating = 4
                if index:
                    room_type = "Private room"
                    rating = 0
                listings.append({
                    "snapshot_date": snapshot, "listing_id": listing,
                    "neighbourhood_cleansed": "A", "room_type": room_type,
                    "price_cad": price, "price_valid": "true",
                    "price_outlier_flag": "false", "room_type_valid": "true",
                    "review_scores_rating": rating,
                })
                for day_index, day in enumerate(pd.date_range(snapshot, periods=10)):
                    calendar_days.append({
                        "listing_id": listing, "date_parsed": day,
                        "available_valid": True, "available_true": day_index < 5,
                    })
            summary = qa.calendar_listing_summary(pd.DataFrame(calendar_days))
            summary.insert(0, "snapshot_date", snapshot)
            calendars.extend(summary.to_dict("records"))
        listing_frame = pd.DataFrame(listings)
        listing_frame["rating_valid"] = qa.check_rating(listing_frame)["rating_valid"]
        write_csv(input_dir / kpi.LISTINGS_FILE, listing_frame.to_dict("records"))
        write_csv(input_dir / kpi.CALENDAR_FILE, calendars)
        config = {
            "input_dir": str(input_dir), "output_dir": str(self.folder / "kpi"),
            "checks_path": str(self.folder / "checks.csv"), "llm_file": str(self.output),
        }
        result = kpi.run(config)
        self.assertEqual(len(result["outputs"]), 8)
        self.assertEqual(result["warnings"], 0)
        for output in result["outputs"].values():
            self.assertTrue(Path(output).is_file())
        checks = pd.read_csv(result["checks"])
        self.assertTrue(checks["status"].eq("PASS").all())
        snapshot = pd.read_csv(result["outputs"]["kpi_snapshot.csv"]).iloc[-1]
        self.assertEqual(snapshot["n_listings"], 2)
        self.assertEqual(snapshot["median_price_cad"], 150)
        self.assertEqual(snapshot["entire_home_share"], 0.5)
        self.assertEqual(snapshot["availability_share_mean"], 0.5)
        self.assertEqual(snapshot["calendar_coverage_mean"], 1)
        self.assertEqual(snapshot["n_rating_valid"], 1)
        self.assertEqual(snapshot["median_rating"], 4)
        time_table = pd.read_csv(result["outputs"]["kpi_time.csv"])
        self.assertEqual(time_table.iloc[-1]["delta_median_price_cad"], 20)
        llm_table = pd.read_csv(result["outputs"]["kpi_llm_snapshot.csv"])
        self.assertEqual(llm_table.iloc[0]["n_llm_usable"], 30)
        self.assertEqual(llm_table.iloc[0]["llm_negative_share"], 0.3333)

    def test_evaluate_handles_mixed_and_keeps_missing_prediction_in_denominator(self):
        rows = []
        labels = []
        predictions = []
        texts = {"positive": "Great", "mixed": "Great but dirty", "negative": "Bad"}
        for index in range(100):
            label = llm.LABELS[index % 3]
            review_id = str(index)
            rows.append({
                "snapshot_date": SNAPSHOT, "review_id": review_id,
                "split": "test", "text": texts[label],
            })
            labels.append({
                "snapshot_date": SNAPSHOT, "review_id": review_id,
                "split": "test", "manual_sentiment": label,
            })
            if index != 1:
                predictions.append({"review_id": review_id, "status": "ok", "sentiment": label})
        labels_path = self.folder / "synthetic_labels.csv"
        reports = self.folder / "evaluation"
        write_csv(labels_path, labels)
        with redirect_stdout(StringIO()):
            llm.evaluate(rows, predictions, str(labels_path), reports)
        metrics = json.loads((reports / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["llm"]["n"], 100)
        self.assertEqual(metrics["llm"]["accuracy"], 0.99)
        self.assertEqual(metrics["llm"]["coverage"], 0.99)
        self.assertEqual(metrics["llm"]["per_class"]["mixed"]["support"], 33)
        self.assertAlmostEqual(metrics["llm"]["macro_f1"], (1 + 64 / 65 + 1) / 3)
        self.assertEqual(metrics["baseline"]["accuracy"], 1)
        labels[0]["manual_sentiment"] = "neutral"
        write_csv(labels_path, labels)
        with self.assertRaisesRegex(ValueError, "positive/mixed/negative"):
            llm.evaluate(rows, predictions, str(labels_path), reports)


if __name__ == "__main__":
    main()
