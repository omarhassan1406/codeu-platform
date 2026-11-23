"""Integration and smoke tests for the CodeU-Backend API.

Run from the repository root:
    .venv/Scripts/python.exe test_backend.py   (Windows; .venv/bin/python elsewhere)

External services (Gemini, Qdrant, the bge-m3 embedding model, and the full
course-generation pipeline) are stubbed so the suite runs fast and offline,
while the real FastAPI app, routing, validation, background-task execution,
and the Gemini fallback wrapper are exercised end-to-end.
"""

import os
import sys
import threading
import types as pytypes
import unittest
from unittest import mock

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# The Qoder shell injects a NO_PROXY value that breaks httpx client creation.
os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from google.genai import errors as genai_errors


class FakeModels:
    def __init__(self):
        self.calls = []
        self.failures = {}

    def generate_content(self, *, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        failure = self.failures.get(model)
        if failure is not None:
            raise failure
        return pytypes.SimpleNamespace(text=f"[{model}] إجابة تجريبية")


class FakeGeminiClient:
    def __init__(self):
        self.models = FakeModels()


class _ExternalServiceGuard:
    def __getattr__(self, name):
        raise AssertionError(f"External service attribute '{name}' must be stubbed in tests")


_ai_clients_stub = pytypes.ModuleType("app.services.ai_clients")
_ai_clients_stub.get_embedding_model = lambda: _ExternalServiceGuard()
_ai_clients_stub.get_qdrant_client = lambda: _ExternalServiceGuard()
_default_gemini = FakeGeminiClient()
_ai_clients_stub.get_gemini_client = lambda: _default_gemini
sys.modules["app.services.ai_clients"] = _ai_clients_stub

from fastapi.testclient import TestClient

import Generate_Course
from app.api.v1.endpoints import tutor as tutor_module
from app.core.config import settings
from app.main import app
from app.services import gemini_service, rag_service
from app.services.rag_service import RagUnavailableError, RetrievedChunk


def make_rate_limit_error(model: str = "test-model") -> genai_errors.ClientError:
    return genai_errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "message": f"Quota exceeded for {model}",
                "status": "RESOURCE_EXHAUSTED",
            }
        },
    )


def make_model_not_found_error(model: str = "test-model") -> genai_errors.ClientError:
    return genai_errors.ClientError(
        404,
        {
            "error": {
                "code": 404,
                "message": f"models/{model} is not found for API version v1beta",
                "status": "NOT_FOUND",
            }
        },
    )


COMPLETE_LESSON = "# Lesson\n\n" + ("Explained concept. " * 60) + "\n```python\nx = 1\n```\n"


def make_roadmap_dict(title="Test Course", sections=2, steps_per_section=4, step_title="Setup"):
    return {
        "course_title": title,
        "target_audience": "Beginners",
        "sections": [
            {
                "section_id": s,
                "section_title": f"Section {s}",
                "description": "Intro",
                "steps": [
                    {
                        "step_id": f"{s}.{n}",
                        "step_title": f"{step_title} {s}.{n}",
                        "duration_mins": 10,
                        "learning_objectives": ["Install Python"],
                    }
                    for n in range(1, steps_per_section + 1)
                ],
            }
            for s in range(1, sections + 1)
        ],
    }


def make_roadmap_json(**kwargs):
    import json

    return json.dumps(make_roadmap_dict(**kwargs))


class ApiSurfaceTests(unittest.TestCase):
    def test_core_routes_are_registered(self):
        paths = app.openapi()["paths"]
        self.assertIn("/", paths)
        self.assertIn("/api/v1/courses/generate", paths)
        self.assertIn("/api/v1/tutor/raise-hand", paths)


class HealthCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_health_check(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "online")
        self.assertIn(settings.PROJECT_NAME, payload["message"])


class CourseGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.pipeline_calls = []
        self.pipeline_done = threading.Event()

        def fake_pipeline(course_topic, on_progress=None):
            self.pipeline_calls.append(course_topic)
            self.pipeline_done.set()

        # mock.patch restores the original function itself (a class attribute
        # would come back as a bound method and break later real calls).
        patcher = mock.patch.object(Generate_Course, "run_codeu_complete_pipeline", fake_pipeline)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_generate_returns_202_and_runs_background_task(self):
        with self.assertLogs("app.api.v1.endpoints.courses", level="INFO") as captured:
            response = self.client.post(
                "/api/v1/courses/generate",
                json={"course_topic": "Python for Beginners"},
            )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "accepted")
        self.assertEqual(payload["course_topic"], "Python for Beginners")
        self.assertIn("background", payload["message"])
        self.assertTrue(self.pipeline_done.wait(timeout=5), "background task did not run")
        self.assertEqual(self.pipeline_calls, ["Python for Beginners"])
        self.assertTrue(any("started" in entry for entry in captured.output))
        self.assertTrue(any("completed" in entry for entry in captured.output))

    def test_topic_is_normalized_before_background_generation(self):
        response = self.client.post(
            "/api/v1/courses/generate",
            json={"course_topic": "  Machine   Learning  "},
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["course_topic"], "Machine Learning")
        self.assertTrue(self.pipeline_done.wait(timeout=5), "background task did not run")
        self.assertEqual(self.pipeline_calls, ["Machine Learning"])

    def test_background_failure_is_logged_not_raised(self):
        def failing_pipeline(course_topic, on_progress=None):
            raise RuntimeError("simulated pipeline failure")

        Generate_Course.run_codeu_complete_pipeline = failing_pipeline
        with self.assertLogs("app.api.v1.endpoints.courses", level="ERROR") as captured:
            response = self.client.post(
                "/api/v1/courses/generate",
                json={"course_topic": "Failing Topic"},
            )

        self.assertEqual(response.status_code, 202)
        self.assertTrue(any("failed" in entry for entry in captured.output))

    def test_invalid_topics_are_rejected(self):
        for topic in ["", "  x  ", "a" * 201]:
            with self.subTest(topic=topic):
                response = self.client.post(
                    "/api/v1/courses/generate",
                    json={"course_topic": topic},
                )
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.pipeline_calls, [])


class TutorRaiseHandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.gemini = FakeGeminiClient()
        self.gemini_patcher = mock.patch.object(
            gemini_service, "get_gemini_client", return_value=self.gemini
        )
        self.gemini_patcher.start()
        self.rag_context = []
        self.rag_calls = []
        self.rag_error = None

        def fake_rag(course_title, student_question, limit=None, min_score=None):
            self.rag_calls.append(
                {
                    "course_title": course_title,
                    "student_question": student_question,
                }
            )
            if self.rag_error is not None:
                raise self.rag_error
            return [
                RetrievedChunk(text=text, score=0.8, step_id="1.1", step_title="Variables")
                for text in self.rag_context
            ]

        self.rag_patcher = mock.patch.object(tutor_module, "search_course_rag", side_effect=fake_rag)
        self.rag_patcher.start()

    def tearDown(self):
        self.rag_patcher.stop()
        self.gemini_patcher.stop()

    def _post_question(self, question="What is a variable?"):
        return self.client.post(
            "/api/v1/tutor/raise-hand",
            json={
                "course_title": "Python for Beginners",
                "step_id": "1.1",
                "student_question": question,
            },
        )

    def test_raise_hand_returns_grounded_answer(self):
        self.rag_context = ["chunk-1", "chunk-2"]

        response = self._post_question()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer_text"], f"[{settings.GEMINI_MODEL_NAME}] إجابة تجريبية")
        self.assertEqual(payload["avatar_state"], "explaining")
        self.assertEqual(payload["context_used"], ["chunk-1", "chunk-2"])
        self.assertEqual(
            self.rag_calls,
            [
                {
                    "course_title": "Python for Beginners",
                    "student_question": "What is a variable?",
                }
            ],
        )

        call = self.gemini.models.calls[0]
        self.assertEqual(call["model"], settings.GEMINI_MODEL_NAME)
        self.assertIn("chunk-1", call["contents"])
        self.assertIn("What is a variable?", call["contents"])
        self.assertIn(tutor_module.NOT_IN_CONTEXT, call["config"].system_instruction)
        self.assertIn("الدرس 1.1: Variables", call["contents"])

    def test_raise_hand_falls_back_on_rate_limit(self):
        self.rag_context = ["chunk-1"]
        self.gemini.models.failures = {
            settings.GEMINI_MODEL_NAME: make_rate_limit_error(settings.GEMINI_MODEL_NAME)
        }

        with self.assertLogs("app.services.gemini_service", level="WARNING") as captured:
            response = self._post_question()

        self.assertEqual(response.status_code, 200)
        fallback_model = gemini_service.build_model_sequence(settings.GEMINI_MODEL_NAME)[1]
        self.assertEqual(response.json()["answer_text"], f"[{fallback_model}] إجابة تجريبية")
        self.assertEqual(response.json()["avatar_state"], "explaining")
        self.assertEqual(
            [call["model"] for call in self.gemini.models.calls],
            [settings.GEMINI_MODEL_NAME, fallback_model],
        )
        self.assertTrue(any("exhausted" in entry for entry in captured.output))

    def test_raise_hand_without_context_returns_idle(self):
        self.rag_context = []

        response = self._post_question()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["avatar_state"], "idle")
        self.assertEqual(payload["context_used"], [])
        self.assertEqual(self.gemini.models.calls, [])

    def test_model_sentinel_declines_instead_of_answering(self):
        self.rag_context = ["chunk-1"]
        self.gemini.models.generate_content = lambda **kw: pytypes.SimpleNamespace(
            text=tutor_module.NOT_IN_CONTEXT
        )

        payload = self._post_question("What is the capital of France?").json()

        self.assertEqual(payload["answer_text"], tutor_module.DECLINE_MESSAGE)
        self.assertEqual(payload["avatar_state"], "idle")
        self.assertEqual(payload["context_used"], [])

    def test_empty_model_answer_declines(self):
        self.rag_context = ["chunk-1"]
        self.gemini.models.generate_content = lambda **kw: pytypes.SimpleNamespace(text=None)

        payload = self._post_question().json()

        self.assertEqual(payload["answer_text"], tutor_module.DECLINE_MESSAGE)
        self.assertEqual(payload["avatar_state"], "idle")

    def test_rag_outage_returns_503_without_calling_model(self):
        self.rag_error = RagUnavailableError("down")

        response = self._post_question()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.gemini.models.calls, [])

    def test_model_failure_returns_502_without_leaking_details(self):
        self.rag_context = ["chunk-1"]
        self.gemini.models.failures = {settings.GEMINI_MODEL_NAME: ValueError("secret-key-xyz invalid")}

        with self.assertLogs("app.api.v1.endpoints.tutor", level="ERROR"):
            response = self._post_question()

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret-key-xyz", response.text)

    def test_endpoint_is_sync_so_blocking_work_runs_in_threadpool(self):
        import inspect

        self.assertFalse(inspect.iscoroutinefunction(tutor_module.raise_hand))


class CourseGeneratorServiceTests(unittest.TestCase):
    def test_roadmap_generation_uses_fallback_wrapper_and_course_model(self):
        captured = {}

        def fake_generation(*, contents, config=None, preferred_model=None):
            captured["preferred_model"] = preferred_model
            captured["config"] = config
            return pytypes.SimpleNamespace(text=make_roadmap_json())

        with mock.patch.object(
            Generate_Course, "generate_content_with_fallback", side_effect=fake_generation
        ):
            roadmap = Generate_Course.generate_course_roadmap("Python")

        self.assertEqual(captured["preferred_model"], settings.GEMINI_COURSE_MODEL)
        self.assertIs(captured["config"].response_schema, Generate_Course.CourseRoadmap)
        self.assertEqual(captured["config"].response_mime_type, "application/json")
        self.assertEqual(roadmap.course_title, "Test Course")
        self.assertEqual(roadmap.sections[0].steps[0].step_id, "1.1")
        self.assertEqual(sum(len(sec.steps) for sec in roadmap.sections), 8)

    def test_step_content_generation_uses_fallback_wrapper_and_course_model(self):
        captured = {}

        def fake_generation(*, contents, config=None, preferred_model=None):
            captured["preferred_model"] = preferred_model
            captured["config"] = config
            captured["contents"] = contents
            return pytypes.SimpleNamespace(text=COMPLETE_LESSON)

        step = Generate_Course.Step(
            step_id="1.1",
            step_title="Setup",
            duration_mins=10,
            learning_objectives=["Install Python"],
        )

        with mock.patch.object(
            Generate_Course, "generate_content_with_fallback", side_effect=fake_generation
        ):
            content = Generate_Course.generate_step_content(
                "Python", "Basics", step, prev_step_title=None
            )

        self.assertEqual(captured["preferred_model"], settings.GEMINI_COURSE_MODEL)
        self.assertIn("Setup", captured["contents"])
        self.assertEqual(captured["config"].temperature, 0.4)
        self.assertEqual(content, COMPLETE_LESSON.strip())


class FallbackConfigurationTests(unittest.TestCase):
    EXPECTED_HIERARCHY = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.0-flash",
        "gemini-2.5-flash",
    ]

    def setUp(self):
        self.gemini = FakeGeminiClient()
        patcher = mock.patch.object(gemini_service, "get_gemini_client", return_value=self.gemini)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_hierarchy_is_ordered_and_prioritizes_primary(self):
        self.assertEqual(settings.GEMINI_MODEL_HIERARCHY, self.EXPECTED_HIERARCHY)
        self.assertEqual(settings.GEMINI_MODEL_HIERARCHY[0], "gemini-3.5-flash-lite")

    def test_build_model_sequence_prepends_preferred_and_dedupes(self):
        self.assertEqual(
            gemini_service.build_model_sequence("gemini-3.5-flash-lite"),
            self.EXPECTED_HIERARCHY,
        )
        tutor_sequence = gemini_service.build_model_sequence("gemini-2.0-flash")
        self.assertEqual(tutor_sequence[0], "gemini-2.0-flash")
        self.assertEqual(tutor_sequence[1:], self.EXPECTED_HIERARCHY)

    def test_rate_limit_detection(self):
        self.assertTrue(gemini_service.is_rate_limit_error(make_rate_limit_error()))
        self.assertTrue(gemini_service.is_rate_limit_error(Exception("HTTP 429 Too Many Requests")))
        self.assertFalse(gemini_service.is_rate_limit_error(ValueError("invalid API key")))

    def test_wrapper_falls_back_on_429_and_logs_exhaustion(self):
        self.gemini.models.failures = {
            "gemini-3.5-flash-lite": make_rate_limit_error("gemini-3.5-flash-lite"),
            "gemini-3.1-flash-lite": make_rate_limit_error("gemini-3.1-flash-lite"),
        }

        with self.assertLogs("app.services.gemini_service", level="WARNING") as captured:
            response = gemini_service.generate_content_with_fallback(
                contents="hello",
                preferred_model="gemini-3.5-flash-lite",
            )

        self.assertEqual(
            [call["model"] for call in self.gemini.models.calls],
            ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash"],
        )
        self.assertEqual(response.text, "[gemini-3.8-flash] إجابة تجريبية")
        self.assertEqual(sum("exhausted" in entry for entry in captured.output), 2)

    def test_model_unavailable_detection(self):
        self.assertTrue(gemini_service.is_model_unavailable_error(make_model_not_found_error()))
        self.assertFalse(gemini_service.is_model_unavailable_error(make_rate_limit_error()))
        self.assertFalse(gemini_service.is_model_unavailable_error(ValueError("invalid API key")))

    def test_wrapper_skips_retired_model(self):
        # Live check found gemini-2.0-flash returns 404 NOT_FOUND on the project key.
        self.gemini.models.failures = {"gemini-2.0-flash": make_model_not_found_error("gemini-2.0-flash")}

        with self.assertLogs("app.services.gemini_service", level="WARNING") as captured:
            response = gemini_service.generate_content_with_fallback(
                contents="hello",
                preferred_model="gemini-2.0-flash",
            )

        self.assertEqual(
            [call["model"] for call in self.gemini.models.calls],
            ["gemini-2.0-flash", "gemini-3.5-flash-lite"],
        )
        self.assertEqual(response.text, "[gemini-3.5-flash-lite] إجابة تجريبية")
        self.assertTrue(any("unavailable" in entry for entry in captured.output))

    def test_all_models_unavailable_raises_last_error(self):
        self.gemini.models.failures = {
            model: make_model_not_found_error(model)
            for model in gemini_service.build_model_sequence("gemini-2.0-flash")
        }
        with self.assertLogs("app.services.gemini_service", level="WARNING"):
            with self.assertRaises(genai_errors.ClientError):
                gemini_service.generate_content_with_fallback(contents="hello", preferred_model="gemini-2.0-flash")

    def test_default_tutor_model_is_a_listed_model(self):
        self.assertIn(settings.GEMINI_MODEL_NAME, settings.GEMINI_MODEL_HIERARCHY)
        self.assertIn(settings.GEMINI_COURSE_MODEL, settings.GEMINI_MODEL_HIERARCHY)

    def test_wrapper_propagates_non_rate_limit_errors(self):
        self.gemini.models.failures = {"gemini-3.5-flash-lite": ValueError("invalid API key")}

        with self.assertRaises(ValueError):
            gemini_service.generate_content_with_fallback(
                contents="hello",
                preferred_model="gemini-3.5-flash-lite",
            )

        self.assertEqual(
            [call["model"] for call in self.gemini.models.calls],
            ["gemini-3.5-flash-lite"],
        )

    def test_wrapper_raises_when_all_models_are_exhausted(self):
        self.gemini.models.failures = {
            model: make_rate_limit_error(model) for model in self.EXPECTED_HIERARCHY
        }

        with self.assertRaises(genai_errors.ClientError) as captured:
            gemini_service.generate_content_with_fallback(
                contents="hello",
                preferred_model="gemini-3.5-flash-lite",
            )

        self.assertEqual(captured.exception.code, 429)
        self.assertEqual(
            [call["model"] for call in self.gemini.models.calls],
            self.EXPECTED_HIERARCHY,
        )


class FakeHit:
    def __init__(self, score, text, step_id="1.1"):
        self.score = score
        self.payload = {"text": text, "step_id": step_id, "step_title": "Variables"}


class FakeEmbedding:
    def encode(self, text):
        return pytypes.SimpleNamespace(tolist=lambda: [0.1, 0.2])


class RagServiceTests(unittest.TestCase):
    def setUp(self):
        self.qdrant = mock.Mock()
        for name, value in (("get_embedding_model", FakeEmbedding()), ("get_qdrant_client", self.qdrant)):
            patcher = mock.patch.object(rag_service, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_filters_by_course_and_drops_weak_or_empty_hits(self):
        self.qdrant.query_points.return_value = pytypes.SimpleNamespace(
            points=[FakeHit(0.82, "strong"), FakeHit(0.10, "weak"), FakeHit(0.9, "   ")]
        )

        chunks = rag_service.search_course_rag("Py", "q", limit=5, min_score=0.5)

        self.assertEqual([c.text for c in chunks], ["strong"])
        self.assertEqual(chunks[0].step_id, "1.1")
        kwargs = self.qdrant.query_points.call_args.kwargs
        self.assertEqual(kwargs["score_threshold"], 0.5)
        self.assertEqual(kwargs["limit"], 5)
        condition = kwargs["query_filter"].must[0]
        self.assertEqual((condition.key, condition.match.value), ("course_title", "Py"))

    def test_uses_configured_defaults(self):
        self.qdrant.query_points.return_value = pytypes.SimpleNamespace(points=[])

        rag_service.search_course_rag("Py", "q")

        kwargs = self.qdrant.query_points.call_args.kwargs
        self.assertEqual(kwargs["limit"], settings.RAG_TOP_K)
        self.assertEqual(kwargs["score_threshold"], settings.RAG_MIN_SCORE)

    def test_qdrant_failure_raises_instead_of_returning_empty(self):
        self.qdrant.query_points.side_effect = ConnectionError("timeout")

        with self.assertLogs("app.services.rag_service", level="ERROR"):
            with self.assertRaises(RagUnavailableError):
                rag_service.search_course_rag("Py", "q")


class LazyLoadingAndPointIdTests(unittest.TestCase):
    def _run_fresh_python(self, code):
        import subprocess

        env = dict(os.environ, PYTHONHASHSEED="random")
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=BASE_DIR, env=env,
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip().splitlines()[-1]

    def test_importing_app_and_pipeline_does_not_load_embedding_model(self):
        out = self._run_fresh_python(
            "import sys, app.main, Generate_Course; "
            "print('sentence_transformers' in sys.modules)"
        )
        self.assertEqual(out, "False")

    def test_point_ids_are_stable_across_processes(self):
        code = "import Generate_Course as g; print(g.make_point_id('Py Course', '1.1', 0))"
        first, second = self._run_fresh_python(code), self._run_fresh_python(code)
        self.assertEqual(first, second)
        self.assertEqual(first, Generate_Course.make_point_id("Py Course", "1.1", 0))

    def test_point_ids_are_valid_and_distinct(self):
        import uuid

        ids = {
            Generate_Course.make_point_id("A", "1.1", 0),
            Generate_Course.make_point_id("A", "1.1", 1),
            Generate_Course.make_point_id("A", "1.2", 0),
            Generate_Course.make_point_id("B", "1.1", 0),
        }
        self.assertEqual(len(ids), 4)
        for value in ids:
            uuid.UUID(value)


class CompletenessValidationTests(unittest.TestCase):
    def roadmap(self, **kwargs):
        return Generate_Course.CourseRoadmap.model_validate(make_roadmap_dict(**kwargs))

    def test_complete_roadmap_has_no_problems(self):
        self.assertEqual(Generate_Course.validate_roadmap(self.roadmap(), 4), [])

    def test_roadmap_problems_are_detected(self):
        self.assertTrue(Generate_Course.validate_roadmap(self.roadmap(sections=0), 4))
        self.assertTrue(Generate_Course.validate_roadmap(self.roadmap(steps_per_section=2), 4))

        data = make_roadmap_dict()
        data["sections"][1]["steps"][0]["step_id"] = "1.1"
        data["sections"][0]["steps"][1]["learning_objectives"] = ["  "]
        data["sections"][0]["steps"][2]["step_title"] = ""
        problems = Generate_Course.validate_roadmap(
            Generate_Course.CourseRoadmap.model_validate(data), 4
        )
        joined = " | ".join(problems)
        self.assertIn("duplicate step_id", joined)
        self.assertIn("no learning_objectives", joined)
        self.assertIn("empty step_title", joined)

    def test_lesson_checks(self):
        validate = Generate_Course.validate_lesson
        self.assertEqual(validate(COMPLETE_LESSON, "STOP", 100), [])
        self.assertEqual(validate(COMPLETE_LESSON, None, 100), [])
        self.assertIn("empty", validate("  ", "STOP", 100)[0])
        self.assertIn("too short", validate("short", "STOP", 100)[0])
        self.assertIn("finish_reason=MAX_TOKENS", validate(COMPLETE_LESSON, "MAX_TOKENS", 100)[0])
        self.assertIn("unclosed code block", validate(COMPLETE_LESSON + "```py\nx", "STOP", 100)[0])

    def _patch_generation(self, responses):
        calls = []

        def fake(*, contents, config=None, preferred_model=None):
            calls.append(contents)
            return responses[min(len(calls), len(responses)) - 1]

        patcher = mock.patch.object(Generate_Course, "generate_content_with_fallback", side_effect=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def test_incomplete_roadmap_is_retried(self):
        calls = self._patch_generation([
            pytypes.SimpleNamespace(text=make_roadmap_json(steps_per_section=1)),
            pytypes.SimpleNamespace(text=make_roadmap_json()[:40]),  # truncated JSON
            pytypes.SimpleNamespace(text=make_roadmap_json()),
        ])

        with self.assertLogs("Generate_Course", level="WARNING"):
            roadmap = Generate_Course.generate_course_roadmap("Python")

        self.assertEqual(len(calls), 3)
        self.assertEqual(len(roadmap.sections), 2)

    def test_roadmap_fails_explicitly_after_max_attempts(self):
        calls = self._patch_generation([pytypes.SimpleNamespace(text=make_roadmap_json(steps_per_section=1))])

        with self.assertLogs("Generate_Course", level="WARNING"):
            with self.assertRaises(Generate_Course.GenerationIncompleteError):
                Generate_Course.generate_course_roadmap("Python")

        self.assertEqual(len(calls), settings.GENERATION_MAX_ATTEMPTS)

    def test_truncated_lesson_is_regenerated(self):
        truncated = pytypes.SimpleNamespace(
            text=COMPLETE_LESSON,
            candidates=[pytypes.SimpleNamespace(finish_reason=pytypes.SimpleNamespace(name="MAX_TOKENS"))],
        )
        calls = self._patch_generation([truncated, pytypes.SimpleNamespace(text=COMPLETE_LESSON)])
        step = Generate_Course.Step(step_id="1.1", step_title="Setup", duration_mins=10, learning_objectives=["x"])

        with self.assertLogs("Generate_Course", level="WARNING"):
            content = Generate_Course.generate_step_content("Py", "Basics", step)

        self.assertEqual(len(calls), 2)
        self.assertEqual(content, COMPLETE_LESSON.strip())


class PipelineTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ingested = []
        patches = {
            "ensure_collection": mock.Mock(),
            "generate_step_content": mock.Mock(return_value=COMPLETE_LESSON),
            "ingest_lesson_to_qdrant_with_retry": mock.Mock(
                side_effect=lambda **kw: self.ingested.append((kw["course_title"], kw["step_id"]))
            ),
        }
        self.mocks = {}
        for name, value in patches.items():
            patcher = mock.patch.object(Generate_Course, name, value)
            self.mocks[name] = patcher.start()
            self.addCleanup(patcher.stop)

    def _run(self, title):
        roadmap = Generate_Course.CourseRoadmap.model_validate(make_roadmap_dict(title=title))
        with mock.patch.object(Generate_Course, "generate_course_roadmap", return_value=roadmap):
            return Generate_Course.run_codeu_complete_pipeline(title, output_dir=self.tmp.name)

    def _read_json(self, *parts):
        import json

        with open(os.path.join(self.tmp.name, *parts), encoding="utf-8") as f:
            return json.load(f)

    def test_courses_with_same_step_titles_do_not_overwrite_each_other(self):
        self._run("Course A")
        self._run("Course B")

        for title, folder in (("Course A", "Course_A"), ("Course B", "Course_B")):
            files = sorted(os.listdir(os.path.join(self.tmp.name, folder)))
            self.assertIn("roadmap.json", files)
            self.assertIn("step_1.1_Setup_1.1.md", files)
            self.assertEqual(len([f for f in files if f.endswith(".md")]), 8)
            manifest = self._read_json(folder, "manifest.json")
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(len(manifest["completed_steps"]), 8)
            self.assertEqual(self._read_json(folder, "roadmap.json")["course_title"], title)
        self.assertEqual(len(self.ingested), 16)

    def test_failed_lesson_marks_course_failed_and_raises(self):
        self.mocks["generate_step_content"].side_effect = [
            COMPLETE_LESSON,
            Generate_Course.GenerationIncompleteError("lesson 1.2 truncated"),
        ]

        with self.assertRaises(Generate_Course.GenerationIncompleteError):
            self._run("Course A")

        manifest = self._read_json("Course_A", "manifest.json")
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["completed_steps"], ["1.1"])
        self.assertIn("lesson 1.2 truncated", manifest["error"])


class IngestionTests(unittest.TestCase):
    def test_ingestion_replaces_old_chunks_with_deterministic_ids(self):
        qdrant = mock.Mock()
        with mock.patch.object(Generate_Course, "get_qdrant_client", return_value=qdrant), \
             mock.patch.object(Generate_Course, "get_embedding_model", return_value=FakeEmbedding()):
            Generate_Course.ingest_lesson_to_qdrant_with_retry("Py", "Basics", "1.1", "Setup", "word " * 600)

        delete_filter = qdrant.delete.call_args.kwargs["points_selector"].filter
        self.assertEqual(
            [(c.key, c.match.value) for c in delete_filter.must],
            [("course_title", "Py"), ("step_id", "1.1")],
        )
        points = qdrant.upsert.call_args.kwargs["points"]
        expected_chunks = chunking.get_chunker().split("word " * 600)
        self.assertEqual(len(points), len(expected_chunks))
        self.assertGreater(len(points), 1)
        self.assertEqual(points[0].id, Generate_Course.make_point_id("Py", "1.1", 0))
        self.assertEqual(points[0].payload["chunk_strategy"], settings.CHUNK_STRATEGY)

    def test_ingestion_failure_is_raised_after_retries(self):
        qdrant = mock.Mock()
        qdrant.upsert.side_effect = ConnectionError("down")
        with mock.patch.object(Generate_Course, "get_qdrant_client", return_value=qdrant), \
             mock.patch.object(Generate_Course, "get_embedding_model", return_value=FakeEmbedding()), \
             mock.patch.object(Generate_Course.time, "sleep"):
            with self.assertRaises(Generate_Course.IngestionError):
                Generate_Course.ingest_lesson_to_qdrant_with_retry("Py", "Basics", "1.1", "Setup", "text")
        self.assertEqual(qdrant.upsert.call_count, 3)

# =====================================================================
# Phase 2A: chunking, reranking, catalog, onboarding, config
# =====================================================================

from pathlib import Path

from app.services import chunking, course_catalog, reranker as reranker_module, suggestions
from app.schemas.courses import CourseSummary
from app.schemas.onboarding import LearnerProfile


def _legacy_word_chunks(text, chunk_size=500, overlap=50):
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size - overlap)]


class ChunkingTests(unittest.TestCase):
    def test_word_chunker_matches_legacy_output(self):
        text = " ".join(f"w{i}" for i in range(1234))
        self.assertEqual(chunking.WordChunker(500, 50).split(text), _legacy_word_chunks(text))
        self.assertEqual(Generate_Course.chunk_text(text), _legacy_word_chunks(text))
        self.assertEqual(Generate_Course.chunk_text(text, 100, 10), _legacy_word_chunks(text, 100, 10))

    def test_character_chunks_respect_size_and_keep_all_words(self):
        text = "# Title\n\n" + "\n\n".join(
            f"Paragraph {p}. " + " ".join(f"word{p}_{i}." for i in range(40)) for p in range(8)
        )
        chunks = chunking.CharacterChunker(600, 120).split(text)

        self.assertGreater(len(chunks), 3)
        self.assertTrue(all(len(c) <= 600 for c in chunks))
        joined = " ".join(chunks)
        for word in text.split():
            self.assertIn(word, joined)

    def test_long_prose_chunks_overlap(self):
        text = " ".join(f"Sentence number {i} explains something." for i in range(80))
        chunks = chunking.CharacterChunker(300, 80).split(text)

        self.assertGreater(len(chunks), 2)
        for previous, current in zip(chunks, chunks[1:]):
            last_sentence = previous.split(". ")[-1].rstrip(".")
            self.assertIn(last_sentence, current)

    def test_code_blocks_stay_fenced_and_keep_line_breaks(self):
        code = "\n".join(f"    value_{i} = compute({i})  # step {i}" for i in range(60))
        text = f"Intro paragraph.\n\n```python\ndef run():\n{code}\n```\n\nOutro."
        chunks = chunking.CharacterChunker(600, 120).split(text)

        code_chunks = [c for c in chunks if "value_" in c]
        self.assertGreater(len(code_chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 600)
            self.assertEqual(chunk.count("```") % 2, 0, chunk)
        for chunk in code_chunks:
            self.assertIn("```python\n", chunk)
            self.assertIn("\n    value_", chunk)  # line structure preserved
        for i in range(60):
            self.assertTrue(any(f"value_{i} = compute({i})" in c for c in chunks))

    def test_small_code_block_is_kept_whole(self):
        text = "Explain.\n\n```python\nx = 1\nprint(x)\n```\n\nDone."
        chunks = chunking.CharacterChunker(600, 120).split(text)
        self.assertEqual(len(chunks), 1)
        self.assertIn("```python\nx = 1\nprint(x)\n```", chunks[0])

    def test_unclosed_fence_is_closed_per_chunk(self):
        text = "Intro.\n\n```python\nx = 1\ny = 2"
        chunks = chunking.CharacterChunker(600, 120).split(text)
        self.assertTrue(all(c.count("```") % 2 == 0 for c in chunks))
        self.assertIn("y = 2", chunks[-1])

    def test_real_generated_lesson_chunks_cleanly(self):
        course = os.path.join(BASE_DIR, "generated_courses", "Programming_in_Python_for_Beginners_to_Advanced")
        lesson = next(f for f in os.listdir(course) if f.startswith("step_1.2_"))
        with open(os.path.join(course, lesson), encoding="utf-8") as f:
            text = f.read()
        chunks = chunking.get_chunker("character").split(text)
        self.assertTrue(chunks)
        self.assertTrue(all(len(c) <= settings.CHUNK_SIZE_CHARS for c in chunks))
        self.assertTrue(all(c.count("```") % 2 == 0 for c in chunks))

    def test_get_chunker_uses_settings_and_validates(self):
        self.assertIsInstance(chunking.get_chunker(), chunking.CharacterChunker)
        with mock.patch.object(settings, "CHUNK_STRATEGY", "word"):
            self.assertIsInstance(chunking.get_chunker(), chunking.WordChunker)
        chunker = chunking.get_chunker("character")
        self.assertEqual((chunker.chunk_size, chunker.overlap), (600, 120))
        with self.assertRaises(ValueError):
            chunking.get_chunker("sentences")
        with self.assertRaises(ValueError):
            chunking.CharacterChunker(100, 100)


class FakeCrossEncoder:
    def predict(self, pairs):
        # Higher score for chunks containing the word "best".
        return [10.0 if "best" in text else float(len(text)) / 100 for _, text in pairs]


class RerankerTests(unittest.TestCase):
    def chunks(self):
        return [
            RetrievedChunk(text="ok", score=0.9),
            RetrievedChunk(text="the best one", score=0.6),
            RetrievedChunk(text="fine", score=0.7),
        ]

    def test_noop_keeps_order_and_truncates(self):
        result = reranker_module.NoOpReranker().rerank("q", self.chunks(), 2)
        self.assertEqual([c.text for c in result], ["ok", "the best one"])

    def test_cross_encoder_reorders_and_records_scores(self):
        result = reranker_module.CrossEncoderReranker(model=FakeCrossEncoder()).rerank("q", self.chunks(), 2)
        self.assertEqual(result[0].text, "the best one")
        self.assertEqual(result[0].rerank_score, 10.0)
        self.assertEqual(len(result), 2)

    def test_get_reranker_by_name(self):
        self.assertIsInstance(reranker_module.get_reranker(), reranker_module.NoOpReranker)
        bge = reranker_module.get_reranker("bge")
        self.assertIsInstance(bge, reranker_module.CrossEncoderReranker)
        self.assertIs(bge, reranker_module.get_reranker("bge"))  # cached, model loads once
        self.assertIsNone(bge._model)  # not loaded until first rerank
        with self.assertRaises(ValueError):
            reranker_module.get_reranker("cohere")

    def _search_with(self, reranker):
        qdrant = mock.Mock()
        qdrant.query_points.return_value = pytypes.SimpleNamespace(
            points=[FakeHit(0.9, "ok"), FakeHit(0.6, "the best one"), FakeHit(0.7, "fine")]
        )
        with mock.patch.object(rag_service, "get_embedding_model", return_value=FakeEmbedding()), \
             mock.patch.object(rag_service, "get_qdrant_client", return_value=qdrant):
            result = rag_service.search_course_rag("Py", "q", limit=2, min_score=0.5, reranker=reranker)
        return result, qdrant.query_points.call_args.kwargs

    def test_rag_fetches_candidates_then_reranks_to_top_k(self):
        result, kwargs = self._search_with(reranker_module.CrossEncoderReranker(model=FakeCrossEncoder()))
        self.assertEqual(kwargs["limit"], settings.RAG_RERANK_CANDIDATES)
        self.assertEqual([c.text for c in result][0], "the best one")
        self.assertEqual(len(result), 2)

    def test_rag_without_reranker_fetches_only_top_k(self):
        result, kwargs = self._search_with(reranker_module.NoOpReranker())
        self.assertEqual(kwargs["limit"], 2)
        self.assertEqual([c.text for c in result], ["ok", "the best one"])

    def test_reranker_failure_falls_back_to_vector_order(self):
        broken = mock.Mock(name="broken")
        broken.rerank.side_effect = RuntimeError("model crashed")
        with self.assertLogs("app.services.rag_service", level="ERROR"):
            result, _ = self._search_with(broken)
        self.assertEqual([c.text for c in result], ["ok", "the best one"])


def write_course(base, folder, roadmap, lessons=None, manifest=None):
    """Create a course folder; ``lessons`` is a list of step ids to write (default: all)."""
    import json
    from app.core.course_paths import lesson_filename

    path = os.path.join(base, folder)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "roadmap.json"), "w", encoding="utf-8") as f:
        f.write(roadmap if isinstance(roadmap, str) else json.dumps(roadmap))
    if isinstance(roadmap, dict):
        for section in roadmap["sections"]:
            for step in section["steps"]:
                if lessons is None or step["step_id"] in lessons:
                    name = lesson_filename(step["step_id"], step["step_title"])
                    with open(os.path.join(path, name), "w", encoding="utf-8") as f:
                        f.write(f"# {section['section_title']}\n## {step['step_title']}\n\nBody {step['step_id']}")
    if manifest is not None:
        with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)
    return path


class CatalogServiceTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = tmp.name
        write_course(self.base, "Done", make_roadmap_dict(title="Done Course"), manifest={"status": "complete"})
        write_course(self.base, "Legacy", make_roadmap_dict(title="Legacy Course"))
        write_course(self.base, "Partial", make_roadmap_dict(title="Partial Course"), lessons=["1.1"])
        write_course(self.base, "Broken", make_roadmap_dict(title="Broken Course"), manifest={"status": "failed"})
        write_course(self.base, "Garbage", "{not json")
        os.makedirs(os.path.join(self.base, "EmptyFolder"))

    def test_lists_courses_with_derived_status(self):
        courses = {c.course_id: c for c in course_catalog.list_courses(self.base)}

        self.assertEqual(set(courses), {"Done", "Legacy", "Partial", "Broken"})
        self.assertEqual(courses["Done"].status, "complete")
        self.assertEqual(courses["Legacy"].status, "complete")
        self.assertEqual(courses["Partial"].status, "incomplete")
        self.assertEqual(courses["Broken"].status, "failed")
        self.assertEqual(courses["Partial"].available_lessons_count, 1)
        self.assertEqual(courses["Done"].lessons_count, 8)
        self.assertEqual(courses["Done"].total_duration_mins, 80)
        self.assertEqual(courses["Done"].title, "Done Course")
        self.assertEqual(courses["Done"].section_titles, ["Section 1", "Section 2"])

    def test_status_filter(self):
        ids = [c.course_id for c in course_catalog.list_courses(self.base, status="complete")]
        self.assertEqual(ids, ["Done", "Legacy"])

    def test_course_detail_marks_available_lessons(self):
        detail = course_catalog.get_course("Partial", self.base)
        steps = [s for section in detail.sections for s in section.steps]
        self.assertEqual([s.step_id for s in steps if s.available], ["1.1"])

    def test_unknown_or_traversal_ids_are_not_found(self):
        for bad in ("Nope", "../Done", "..", "Garbage", "EmptyFolder", "Done/../Legacy"):
            with self.assertRaises(course_catalog.CourseNotFoundError, msg=bad):
                course_catalog.get_course(bad, self.base)

    def test_lesson_detail_with_neighbours(self):
        lesson = course_catalog.get_lesson("Done", "1.4", self.base)
        self.assertEqual((lesson.previous_step_id, lesson.next_step_id), ("1.3", "2.1"))
        self.assertEqual(lesson.section_title, "Section 1")
        self.assertIn("Body 1.4", lesson.content_markdown)

        first = course_catalog.get_lesson("Done", "1.1", self.base)
        last = course_catalog.get_lesson("Done", "2.4", self.base)
        self.assertIsNone(first.previous_step_id)
        self.assertIsNone(last.next_step_id)

    def test_missing_lesson_file_or_step_is_not_found(self):
        with self.assertRaises(course_catalog.LessonNotFoundError):
            course_catalog.get_lesson("Partial", "1.2", self.base)
        with self.assertRaises(course_catalog.LessonNotFoundError):
            course_catalog.get_lesson("Done", "9.9", self.base)

    def test_repository_courses_are_listed(self):
        courses = course_catalog.list_courses(os.path.join(BASE_DIR, "generated_courses"))
        titles = {c.title: c for c in courses}
        self.assertIn("Programming in Python for Beginners to Advanced", titles)
        self.assertTrue(all(c.status == "complete" for c in courses))


class CatalogApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write_course(tmp.name, "Done & Dusted", make_roadmap_dict(title="Done Course"), manifest={"status": "complete"})
        write_course(tmp.name, "Partial", make_roadmap_dict(title="Partial Course"), lessons=["1.1"])
        patcher = mock.patch.object(settings, "GENERATED_COURSES_DIR", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_list_and_filter(self):
        self.assertEqual(len(self.client.get("/api/v1/courses").json()), 2)
        complete = self.client.get("/api/v1/courses", params={"status": "complete"}).json()
        self.assertEqual([c["course_id"] for c in complete], ["Done & Dusted"])
        self.assertEqual(self.client.get("/api/v1/courses", params={"status": "bogus"}).status_code, 422)

    def test_course_and_lesson_endpoints(self):
        from urllib.parse import quote

        cid = quote("Done & Dusted")
        detail = self.client.get(f"/api/v1/courses/{cid}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["sections"]), 2)

        lesson = self.client.get(f"/api/v1/courses/{cid}/lessons/2.1")
        self.assertEqual(lesson.status_code, 200)
        self.assertEqual(lesson.json()["previous_step_id"], "1.4")

    def test_not_found_responses(self):
        self.assertEqual(self.client.get("/api/v1/courses/Nope").json()["detail"], "Course not found")
        self.assertEqual(self.client.get("/api/v1/courses/Nope").status_code, 404)
        missing = self.client.get("/api/v1/courses/Partial/lessons/1.2")
        self.assertEqual((missing.status_code, missing.json()["detail"]), (404, "Lesson not found"))

    def test_generate_route_still_accepts_post(self):
        paths = app.openapi()["paths"]
        self.assertIn("post", paths["/api/v1/courses/generate"])
        self.assertIn("get", paths["/api/v1/courses"])


def make_summary(course_id, title, status="complete", audience="Everyone", sections=()):
    return CourseSummary(
        course_id=course_id, title=title, target_audience=audience, status=status,
        sections_count=len(sections), lessons_count=4, available_lessons_count=4,
        total_duration_mins=40, section_titles=list(sections),
    )


class OnboardingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.courses = [
            make_summary("py", "Programming in Python for Beginners", sections=["Python basics"]),
            make_summary("fl", "Advanced Flutter State Management", sections=["Riverpod", "BLoC"]),
            make_summary("wip", "Calculus Fundamentals", status="in_progress"),
        ]

    def profile(self, **kwargs):
        data = {"interests": ["Python", "Calculus"], "level": "beginner"}
        data.update(kwargs)
        return LearnerProfile(**data)

    def test_mixes_existing_and_generate_suggestions(self):
        result = suggestions.suggest_courses(self.profile(), self.courses)
        kinds = [(s.kind, s.course_id or s.generation_topic) for s in result.suggestions]

        self.assertEqual(kinds, [("existing", "py"), ("generate", "Calculus for Beginners")])
        self.assertEqual(result.strategy, "keyword-v1")

    def test_unfinished_courses_are_never_suggested(self):
        result = suggestions.suggest_courses(self.profile(interests=["Calculus"]), self.courses)
        self.assertTrue(all(s.course_id != "wip" for s in result.suggestions))
        self.assertEqual(result.suggestions[0].kind, "generate")

    def test_section_titles_are_matched_and_list_is_capped(self):
        profile = self.profile(interests=["Riverpod", "Python", "Chemistry", "History"], level="advanced")
        result = suggestions.suggest_courses(profile, self.courses, max_suggestions=3)

        self.assertEqual(len(result.suggestions), 3)
        self.assertEqual({s.kind for s in result.suggestions}, {"existing", "generate"})
        self.assertIn("for Advanced learners", result.suggestions[1].generation_topic)

    def test_profile_validation(self):
        self.assertEqual(self.profile(interests=["  python ", "Python", "SQL"]).interests, ["python", "SQL"])
        for bad in ({"interests": []}, {"interests": ["x"]}, {"level": "guru"}):
            with self.assertRaises(Exception):
                self.profile(**bad)

    def test_endpoint_contract(self):
        with mock.patch.object(course_catalog, "list_courses", return_value=self.courses):
            response = self.client.post(
                "/api/v1/onboarding/suggestions",
                json={"profile": {"interests": ["Python"], "level": "beginner"}, "max_suggestions": 2},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["suggestions"][0]["course_id"], "py")
        self.assertEqual(
            self.client.post("/api/v1/onboarding/suggestions", json={"profile": {"level": "beginner"}}).status_code,
            422,
        )


class ConfigTests(unittest.TestCase):
    def make(self, **env):
        from app.core.config import Settings

        with mock.patch.dict(os.environ, {k: str(v) for k, v in env.items()}):
            return Settings(_env_file=None)

    def test_documented_defaults(self):
        s = self.make()
        self.assertEqual((s.RAG_TOP_K, s.RAG_MIN_SCORE), (3, 0.45))
        self.assertEqual((s.RERANKER, s.RAG_RERANK_CANDIDATES), ("none", 20))
        self.assertEqual((s.CHUNK_STRATEGY, s.CHUNK_SIZE_CHARS, s.CHUNK_OVERLAP_CHARS), ("character", 600, 120))
        self.assertEqual((s.CHUNK_SIZE_WORDS, s.CHUNK_OVERLAP_WORDS), (500, 50))
        self.assertEqual(
            (s.GENERATION_MAX_ATTEMPTS, s.ROADMAP_MIN_STEPS_PER_SECTION, s.LESSON_MIN_CHARS), (3, 4, 800)
        )
        self.assertEqual(s.GENERATED_COURSES_DIR, Path(BASE_DIR).resolve() / "generated_courses")

    def test_env_overrides(self):
        s = self.make(RAG_MIN_SCORE="0.6", CHUNK_STRATEGY="word", ROADMAP_MIN_STEPS_PER_SECTION="5")
        self.assertEqual((s.RAG_MIN_SCORE, s.CHUNK_STRATEGY, s.ROADMAP_MIN_STEPS_PER_SECTION), (0.6, "word", 5))

    def test_invalid_values_are_rejected(self):
        from pydantic import ValidationError

        for env in (
            {"RAG_MIN_SCORE": "1.5"},
            {"RAG_TOP_K": "0"},
            {"CHUNK_STRATEGY": "sentences"},
            {"RERANKER": "cohere"},
            {"CHUNK_SIZE_CHARS": "200", "CHUNK_OVERLAP_CHARS": "200"},
            {"CHUNK_SIZE_WORDS": "50", "CHUNK_OVERLAP_WORDS": "60"},
            {"RERANKER": "bge", "RAG_TOP_K": "5", "RAG_RERANK_CANDIDATES": "3"},
            {"ROADMAP_MIN_STEPS_PER_SECTION": "0"},
        ):
            with self.assertRaises(ValidationError, msg=str(env)):
                self.make(**env)

    def test_env_file_is_resolved_from_project_root(self):
        from app.core.config import Settings

        self.assertEqual(Path(Settings.model_config["env_file"]), Path(BASE_DIR).resolve() / ".env")

class GenerationJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        from app.services import generation_jobs

        self.jobs = generation_jobs
        generation_jobs.clear()
        self.addCleanup(generation_jobs.clear)

    def _start(self, pipeline, topic="Python for Beginners"):
        with mock.patch.object(Generate_Course, "run_codeu_complete_pipeline", pipeline):
            response = self.client.post("/api/v1/courses/generate", json={"course_topic": topic})
        self.assertEqual(response.status_code, 202)
        return response.json()["job_id"]

    def _job(self, job_id):
        response = self.client.get(f"/api/v1/courses/jobs/{job_id}")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_successful_job_reports_progress_and_completion(self):
        seen = {}

        def pipeline(course_topic, on_progress=None):
            seen["callable"] = callable(on_progress)
            on_progress({"course_id": "Py_Course", "course_title": "Py Course",
                         "total_steps": 4, "completed_steps": ["1.1", "1.2"]})

        job = self._job(self._start(pipeline))
        self.assertTrue(seen["callable"])
        self.assertEqual(job["status"], "complete")
        self.assertEqual(job["course_id"], "Py_Course")
        self.assertEqual(job["course_title"], "Py Course")
        self.assertEqual((job["completed_steps"], job["total_steps"]), (2, 4))
        self.assertIsNone(job["error"])
        self.assertEqual(job["course_topic"], "Python for Beginners")

    def test_failed_job_reports_safe_message(self):
        def pipeline(course_topic, on_progress=None):
            raise RuntimeError("secret internal detail")

        with self.assertLogs("app.api.v1.endpoints.courses", level="ERROR"):
            job = self._job(self._start(pipeline))
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], self.jobs.FAILED_MESSAGE)
        self.assertNotIn("secret", job["error"])

    def test_incomplete_generation_gets_its_own_message(self):
        def pipeline(course_topic, on_progress=None):
            raise Generate_Course.GenerationIncompleteError("truncated")

        with self.assertLogs("app.api.v1.endpoints.courses", level="ERROR"):
            job = self._job(self._start(pipeline))
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], self.jobs.INCOMPLETE_MESSAGE)

    def test_new_job_is_queued_until_the_worker_starts(self):
        job = self.jobs.create_job("Topic")
        self.assertEqual(job.status, "queued")
        self.assertEqual(self.jobs.get_job(job.job_id).status, "queued")
        self.jobs.mark_running(job.job_id)
        self.assertEqual(self.jobs.get_job(job.job_id).status, "running")

    def test_unknown_job_returns_404(self):
        response = self.client.get("/api/v1/courses/jobs/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Job not found"})

    def test_pipeline_reports_progress_after_each_lesson(self):
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        updates = []
        roadmap = Generate_Course.CourseRoadmap.model_validate(make_roadmap_dict(title="Course A"))
        with mock.patch.object(Generate_Course, "ensure_collection"), \
                mock.patch.object(Generate_Course, "generate_course_roadmap", return_value=roadmap), \
                mock.patch.object(Generate_Course, "generate_step_content", return_value=COMPLETE_LESSON), \
                mock.patch.object(Generate_Course, "ingest_lesson_to_qdrant_with_retry"):
            Generate_Course.run_codeu_complete_pipeline("Course A", output_dir=tmp.name, on_progress=updates.append)

        self.assertEqual(updates[0]["status"], "in_progress")
        self.assertEqual(updates[0]["completed_steps"], [])
        self.assertEqual(updates[-1]["status"], "complete")
        self.assertEqual(len(updates[-1]["completed_steps"]), 8)
        self.assertEqual({u["course_id"] for u in updates}, {"Course_A"})
        # Each update is a snapshot, not the live manifest list.
        self.assertEqual([len(u["completed_steps"]) for u in updates[:3]], [0, 1, 2])

    def test_broken_progress_callback_does_not_stop_generation(self):
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        roadmap = Generate_Course.CourseRoadmap.model_validate(make_roadmap_dict(title="Course A"))

        def broken(update):
            raise ValueError("boom")

        with mock.patch.object(Generate_Course, "ensure_collection"), \
                mock.patch.object(Generate_Course, "generate_course_roadmap", return_value=roadmap), \
                mock.patch.object(Generate_Course, "generate_step_content", return_value=COMPLETE_LESSON), \
                mock.patch.object(Generate_Course, "ingest_lesson_to_qdrant_with_retry"), \
                self.assertLogs(level="ERROR"):
            result = Generate_Course.run_codeu_complete_pipeline("Course A", output_dir=tmp.name, on_progress=broken)
        self.assertEqual(result.course_title, "Course A")


class ReingestTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        import reingest_courses

        self.reingest = reingest_courses
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def _write_course(self, title="Course A", skip=()):
        import json

        from app.core.course_paths import course_dir, lesson_filename

        roadmap = make_roadmap_dict(title=title)
        folder = course_dir(self.base, title)
        folder.mkdir(parents=True)
        (folder / "roadmap.json").write_text(json.dumps(roadmap), encoding="utf-8")
        for section in roadmap["sections"]:
            for step in section["steps"]:
                if step["step_id"] in skip:
                    continue
                text = f"# {section['section_title']}\n## {step['step_title']}\n\nBody of {step['step_id']}"
                (folder / lesson_filename(step["step_id"], step["step_title"])).write_text(text, encoding="utf-8")
        return folder, roadmap

    def test_ingests_every_saved_lesson_without_the_saved_header(self):
        folder, roadmap = self._write_course(skip=("2.4",))
        calls = []
        report = self.reingest.reingest_course(folder, lambda **kw: calls.append(kw), lambda text: 2)

        self.assertEqual(report.course_title, "Course A")
        self.assertEqual(report.lessons_ingested, 7)
        self.assertEqual(report.chunks, 14)
        self.assertEqual(report.missing_lessons, ["2.4"])
        first = calls[0]
        self.assertEqual(first["course_title"], "Course A")
        self.assertEqual(first["step_id"], "1.1")
        self.assertEqual(first["section_title"], roadmap["sections"][0]["section_title"])
        self.assertEqual(first["content"], "Body of 1.1")

    def test_dry_run_never_ingests(self):
        folder, _ = self._write_course()
        report = self.reingest.reingest_course(folder, None, lambda text: 1)
        self.assertEqual(report.lessons_ingested, 8)

    def test_header_strip_handles_crlf_and_leaves_other_text_alone(self):
        strip = self.reingest.strip_lesson_header
        self.assertEqual(strip("# S\r\n## T\r\n\r\nBody", "S", "T"), "Body")
        self.assertEqual(strip("No header here", "S", "T"), "No header here")

    def test_reuses_pipeline_ingestion_with_deterministic_ids(self):
        folder, _ = self._write_course()
        qdrant = mock.Mock()
        with mock.patch.object(Generate_Course, "get_qdrant_client", return_value=qdrant), \
                mock.patch.object(Generate_Course, "get_embedding_model") as embed:
            embed.return_value.encode.return_value.tolist.return_value = [0.0]
            self.reingest.reingest_course(folder, Generate_Course.ingest_lesson_to_qdrant_with_retry, lambda t: 1)
            first_ids = [c.kwargs["points"][0].id for c in qdrant.upsert.call_args_list]
            qdrant.reset_mock()
            self.reingest.reingest_course(folder, Generate_Course.ingest_lesson_to_qdrant_with_retry, lambda t: 1)
            second_ids = [c.kwargs["points"][0].id for c in qdrant.upsert.call_args_list]

        self.assertEqual(first_ids, second_ids)
        self.assertEqual(first_ids[0], Generate_Course.make_point_id("Course A", "1.1", 0))
        self.assertEqual(qdrant.delete.call_count, 8)

    def test_cli_rejects_unknown_course_and_dry_runs_known_ones(self):
        import contextlib
        import io as _io

        self._write_course()
        out = _io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(_io.StringIO()):
            self.assertEqual(self.reingest.main(["--base-dir", str(self.base), "--course", "Nope"]), 2)
            self.assertEqual(self.reingest.main(["--base-dir", str(self.base), "--dry-run"]), 0)
        self.assertIn("OK      Course_A: 8 lessons", out.getvalue())

if __name__ == "__main__":
    unittest.main(verbosity=2)
