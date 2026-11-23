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
_ai_clients_stub.LOCAL_EMBEDDING_DIMENSIONS = 1024
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

        def fake_rag(course_title, student_question, limit=None, min_score=None, step_id=None):
            self.rag_calls.append(
                {
                    "course_title": course_title,
                    "student_question": student_question,
                    "step_id": step_id,
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
                    "step_id": "1.1",
                }
            ],
        )

        call = self.gemini.models.calls[0]
        self.assertEqual(call["model"], settings.GEMINI_MODEL_NAME)
        self.assertIn("chunk-1", call["contents"])
        self.assertIn("What is a variable?", call["contents"])
        self.assertIn(tutor_module.NOT_IN_CONTEXT, call["config"].system_instruction)
        self.assertIn("الدرس الحالي 1.1: Variables", call["contents"])

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
    def __init__(self, score, text, step_id="1.1", point_id=None):
        self.id = point_id or f"{step_id}:{text}"
        self.score = score
        self.payload = {"text": text, "step_id": step_id, "step_title": "Variables"}


class FakeEmbedder:
    name = "fake"
    model = "fake-embed"
    dimensions = 2

    def embed_query(self, text):
        return [0.1, 0.2]

    def embed_documents(self, texts):
        return [[0.1, 0.2] for _ in texts]


class RagServiceTests(unittest.TestCase):
    def setUp(self):
        self.qdrant = mock.Mock()
        for name, value in (("get_embedder", FakeEmbedder()), ("get_qdrant_client", self.qdrant)):
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
             mock.patch.object(Generate_Course, "get_embedder", return_value=FakeEmbedder()):
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
        self.assertEqual(points[0].payload["embedding_model"], "fake:fake-embed:2")
        self.assertEqual(points[0].vector, [0.1, 0.2])

    def test_ingestion_failure_is_raised_after_retries(self):
        qdrant = mock.Mock()
        qdrant.upsert.side_effect = ConnectionError("down")
        with mock.patch.object(Generate_Course, "get_qdrant_client", return_value=qdrant), \
             mock.patch.object(Generate_Course, "get_embedder", return_value=FakeEmbedder()), \
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
        with mock.patch.object(rag_service, "get_embedder", return_value=FakeEmbedder()), \
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
        self.assertEqual((s.RAG_TOP_K, s.RAG_MIN_SCORE), (3, 0.64))
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
                mock.patch.object(Generate_Course, "get_embedder", return_value=FakeEmbedder()):
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

# =====================================================================
# Embedding providers and collection sizing
# =====================================================================


class FakeEmbedModels:
    def __init__(self, dims=4, failures=None, fold=False):
        self.calls = []
        self.dims = dims
        self.failures = list(failures or [])
        self.fold = fold

    def embed_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": list(contents), "config": config})
        if self.failures:
            raise self.failures.pop(0)
        count = 1 if self.fold else len(contents)
        return pytypes.SimpleNamespace(
            embeddings=[pytypes.SimpleNamespace(values=[float(i)] * self.dims) for i in range(count)]
        )


class EmbeddingProviderTests(unittest.TestCase):
    def setUp(self):
        from app.services import embeddings

        self.embeddings = embeddings

    def _gemini(self, models, dims=4):
        client = pytypes.SimpleNamespace(models=models)
        return self.embeddings.GeminiEmbedder("gemini-embedding-001", dims, client=client, sleep=lambda s: None)

    def test_defaults_are_cloud_friendly(self):
        self.assertEqual(settings.EMBEDDING_PROVIDER, "gemini")
        self.assertEqual(settings.GEMINI_EMBEDDING_MODEL, "gemini-embedding-001")
        self.assertEqual(settings.EMBEDDING_DIMENSIONS, 768)
        embedder = self.embeddings.get_embedder()
        self.assertIsInstance(embedder, self.embeddings.GeminiEmbedder)
        self.assertEqual(embedder.dimensions, 768)

    def test_documents_are_batched_with_document_task_type(self):
        models = FakeEmbedModels()
        vectors = self._gemini(models).embed_documents([f"chunk {i}" for i in range(150)])

        self.assertEqual(len(vectors), 150)
        self.assertEqual([len(c["contents"]) for c in models.calls], [100, 50])
        config = models.calls[0]["config"]
        self.assertEqual(config.task_type, "RETRIEVAL_DOCUMENT")
        self.assertEqual(config.output_dimensionality, 4)
        self.assertEqual(models.calls[0]["model"], "gemini-embedding-001")

    def test_query_uses_query_task_type(self):
        models = FakeEmbedModels()
        vector = self._gemini(models).embed_query("what is a variable?")
        self.assertEqual(vector, [0.0] * 4)
        self.assertEqual(models.calls[0]["config"].task_type, "RETRIEVAL_QUERY")

    def test_empty_document_list_makes_no_call(self):
        models = FakeEmbedModels()
        self.assertEqual(self._gemini(models).embed_documents([]), [])
        self.assertEqual(models.calls, [])

    def test_folded_batch_is_rejected(self):
        # gemini-embedding-2 returns one vector for a multi-text request.
        with self.assertRaises(RuntimeError):
            self._gemini(FakeEmbedModels(fold=True)).embed_documents(["a", "b"])

    def test_wrong_dimension_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self._gemini(FakeEmbedModels(dims=3), dims=4).embed_query("q")

    def test_rate_limit_is_retried(self):
        models = FakeEmbedModels(failures=[make_rate_limit_error("gemini-embedding-001")])
        self.assertEqual(len(self._gemini(models).embed_documents(["a"])), 1)
        self.assertEqual(len(models.calls), 2)

    def test_ingestion_waits_for_the_servers_retry_delay(self):
        # Live: free tier allows 100 embedded texts/minute and asks for ~34s.
        error = genai_errors.ClientError(
            429,
            {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded. Please retry in 34.7s.",
                       "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "34s"}]}},
        )
        waits = []
        client = pytypes.SimpleNamespace(models=FakeEmbedModels(failures=[error]))
        embedder = self.embeddings.GeminiEmbedder("gemini-embedding-001", 4, client=client, sleep=waits.append)
        with self.assertLogs("app.services.embeddings", level="WARNING"):
            embedder.embed_documents(["a"])
        self.assertEqual(waits, [35.0])

    def test_retry_delay_is_capped_and_falls_back_to_backoff(self):
        delay = self.embeddings.retry_delay_seconds
        self.assertEqual(delay(make_rate_limit_error(), attempt=0), 2.0)
        self.assertEqual(delay(make_rate_limit_error(), attempt=2), 8.0)
        huge = genai_errors.ClientError(
            429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "x",
                            "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "900s"}]}}
        )
        self.assertEqual(delay(huge, attempt=0), self.embeddings.MAX_RETRY_WAIT_SECONDS)

    def test_query_does_not_wait_long_when_rate_limited(self):
        # A learner should get a quick 503, not a minute-long hang.
        error = genai_errors.ClientError(
            429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "x",
                            "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "34s"}]}}
        )
        waits = []
        client = pytypes.SimpleNamespace(models=FakeEmbedModels(failures=[error, error]))
        embedder = self.embeddings.GeminiEmbedder("gemini-embedding-001", 4, client=client, sleep=waits.append)
        with self.assertLogs("app.services.embeddings", level="WARNING"), self.assertRaises(genai_errors.ClientError):
            embedder.embed_query("q")
        self.assertLessEqual(sum(waits), self.embeddings.QUERY_MAX_WAIT_SECONDS)

    def test_other_errors_are_not_retried(self):
        models = FakeEmbedModels(failures=[make_model_not_found_error("gemini-embedding-001")])
        with self.assertRaises(genai_errors.ClientError):
            self._gemini(models).embed_query("q")
        self.assertEqual(len(models.calls), 1)

    def test_local_provider_wraps_sentence_transformer(self):
        class FakeST:
            def encode(self, texts):
                if isinstance(texts, str):
                    return [0.5, 0.25]
                return [[0.5, 0.25] for _ in texts]

        local = self.embeddings.LocalEmbedder(model=FakeST())
        self.assertEqual(local.dimensions, 1024)
        self.assertEqual(local.embed_query("q"), [0.5, 0.25])
        self.assertEqual(local.embed_documents(["a", "b"]), [[0.5, 0.25], [0.5, 0.25]])

    def test_unknown_provider_raises(self):
        with self.assertRaises(ValueError):
            self.embeddings.get_embedder("openai")

    def test_cloud_mode_never_imports_torch(self):
        import subprocess

        code = (
            "import sys; import app.main, Generate_Course, reingest_courses; "
            "from app.services import embeddings, rag_service; embeddings.get_embedder(); "
            "bad = [m for m in ('torch', 'sentence_transformers') if m in sys.modules]; "
            "print(bad); sys.exit(1 if bad else 0)"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=BASE_DIR, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class VectorStoreTests(unittest.TestCase):
    def setUp(self):
        from app.services import vector_store

        self.vs = vector_store

    def _client(self, existing_size=None):
        client = mock.Mock()
        client.collection_exists.return_value = existing_size is not None
        client.get_collection.return_value = pytypes.SimpleNamespace(
            config=pytypes.SimpleNamespace(params=pytypes.SimpleNamespace(vectors=pytypes.SimpleNamespace(size=existing_size)))
        )
        return client

    def test_creates_collection_with_model_dimensions_and_indexes(self):
        client = self._client()
        self.assertEqual(self.vs.ensure_collection(768, client=client, name="C"), "created")
        params = client.create_collection.call_args.kwargs["vectors_config"]
        self.assertEqual(params.size, 768)
        indexed = [c.kwargs["field_name"] for c in client.create_payload_index.call_args_list]
        self.assertEqual(indexed, ["course_title", "step_id"])

    def test_matching_collection_is_left_alone(self):
        client = self._client(768)
        self.assertEqual(self.vs.ensure_collection(768, client=client, name="C"), "exists")
        client.delete_collection.assert_not_called()
        client.create_collection.assert_not_called()

    def test_dimension_mismatch_fails_without_deleting(self):
        client = self._client(1024)
        with self.assertRaises(self.vs.CollectionDimensionError) as ctx:
            self.vs.ensure_collection(768, client=client, name="C")
        self.assertIn("--recreate-collection", str(ctx.exception))
        client.delete_collection.assert_not_called()

    def test_dimension_mismatch_with_recreate_rebuilds(self):
        client = self._client(1024)
        with self.assertLogs("app.services.vector_store", level="WARNING"):
            self.assertEqual(self.vs.ensure_collection(768, recreate=True, client=client, name="C"), "recreated")
        client.delete_collection.assert_called_once_with("C")
        self.assertEqual(client.create_collection.call_args.kwargs["vectors_config"].size, 768)

    def test_pipeline_sizes_collection_from_active_embedder(self):
        with mock.patch.object(Generate_Course, "get_embedder", return_value=FakeEmbedder()), \
                mock.patch.object(Generate_Course, "get_qdrant_client", return_value="client"), \
                mock.patch.object(Generate_Course.vector_store, "ensure_collection", return_value="exists") as ensure:
            Generate_Course.ensure_collection(recreate=True)
        ensure.assert_called_once_with(2, recreate=True, client="client")

    def test_reingest_cli_reports_mismatch_and_stops(self):
        import contextlib
        import io as _io
        import tempfile

        import reingest_courses
        from app.services.vector_store import CollectionDimensionError

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        err = _io.StringIO()
        with mock.patch.object(Generate_Course, "ensure_collection", side_effect=CollectionDimensionError("size differs")), \
                contextlib.redirect_stdout(_io.StringIO()), contextlib.redirect_stderr(err):
            code = reingest_courses.main(["--base-dir", tmp.name])
        self.assertEqual(code, 3)
        self.assertIn("size differs", err.getvalue())

    def test_reingest_cli_rejects_dry_run_with_recreate(self):
        import contextlib
        import io as _io

        import reingest_courses

        with contextlib.redirect_stderr(_io.StringIO()), self.assertRaises(SystemExit):
            reingest_courses.main(["--dry-run", "--recreate-collection"])

# =====================================================================
# Phase 3: step-aware retrieval
# =====================================================================


class CountingEmbedder(FakeEmbedder):
    def __init__(self):
        self.queries = 0

    def embed_query(self, text):
        self.queries += 1
        return [0.1, 0.2]


class StepAwareRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.qdrant = mock.Mock()
        self.embedder = CountingEmbedder()
        for name, value in (("get_embedder", self.embedder), ("get_qdrant_client", self.qdrant)):
            patcher = mock.patch.object(rag_service, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _respond(self, lesson_hits, course_hits):
        def query_points(**kwargs):
            keys = [c.key for c in kwargs["query_filter"].must]
            return pytypes.SimpleNamespace(points=lesson_hits if "step_id" in keys else course_hits)

        self.qdrant.query_points.side_effect = query_points

    def _filters(self):
        return [
            [(c.key, c.match.value) for c in call.kwargs["query_filter"].must]
            for call in self.qdrant.query_points.call_args_list
        ]

    def test_current_lesson_chunks_come_first_even_when_others_score_higher(self):
        self._respond(
            lesson_hits=[FakeHit(0.70, "lesson chunk", step_id="1.2")],
            course_hits=[FakeHit(0.90, "other lesson", step_id="3.1"), FakeHit(0.70, "lesson chunk", step_id="1.2")],
        )
        chunks = rag_service.search_course_rag("Py", "q", limit=3, min_score=0.5, step_id="1.2")

        self.assertEqual([c.text for c in chunks], ["lesson chunk", "other lesson"])
        self.assertEqual(self._filters(), [
            [("course_title", "Py"), ("step_id", "1.2")],
            [("course_title", "Py")],
        ])

    def test_question_is_embedded_once_for_both_searches(self):
        self._respond([FakeHit(0.7, "a", step_id="1.2")], [FakeHit(0.8, "b", step_id="2.1")])
        rag_service.search_course_rag("Py", "q", limit=3, min_score=0.5, step_id="1.2")
        self.assertEqual(self.embedder.queries, 1)
        vectors = [call.kwargs["query"] for call in self.qdrant.query_points.call_args_list]
        self.assertEqual(vectors[0], vectors[1])

    def test_no_course_wide_search_when_the_lesson_fills_the_context(self):
        self._respond([FakeHit(0.7, f"l{i}", step_id="1.2") for i in range(3)], [])
        chunks = rag_service.search_course_rag("Py", "q", limit=3, min_score=0.5, step_id="1.2")
        self.assertEqual(len(chunks), 3)
        self.assertEqual(self.qdrant.query_points.call_count, 1)

    def test_falls_back_across_the_course_when_lesson_has_nothing(self):
        self._respond([], [FakeHit(0.8, "from 2.1", step_id="2.1")])
        chunks = rag_service.search_course_rag("Py", "q", limit=3, min_score=0.5, step_id="1.2")
        self.assertEqual([(c.text, c.step_id) for c in chunks], [("from 2.1", "2.1")])

    def test_threshold_applies_to_both_searches(self):
        self._respond([FakeHit(0.3, "weak lesson", step_id="1.2")], [FakeHit(0.2, "weak other", step_id="2.1")])
        chunks = rag_service.search_course_rag("Py", "q", limit=3, min_score=0.5, step_id="1.2")
        self.assertEqual(chunks, [])
        for call in self.qdrant.query_points.call_args_list:
            self.assertEqual(call.kwargs["score_threshold"], 0.5)

    def test_without_step_id_a_single_course_search_runs(self):
        self._respond([], [FakeHit(0.8, "x", step_id="2.1")])
        rag_service.search_course_rag("Py", "q", limit=3, min_score=0.5)
        self.assertEqual(self._filters(), [[("course_title", "Py")]])

    def test_reranker_keeps_lesson_priority(self):
        class ReverseReranker:
            name = "reverse"

            def rerank(self, question, chunks, top_k):
                return list(reversed(chunks))[:top_k]

        self._respond(
            [FakeHit(0.7, "lesson a", step_id="1.2"), FakeHit(0.65, "lesson b", step_id="1.2")],
            [FakeHit(0.9, "other", step_id="3.1")],
        )
        chunks = rag_service.search_course_rag("Py", "q", limit=3, min_score=0.5, step_id="1.2", reranker=ReverseReranker())
        self.assertEqual([c.step_id for c in chunks], ["1.2", "1.2", "3.1"])

    def test_tutor_prompt_marks_current_and_other_lessons(self):
        chunks = [
            RetrievedChunk(text="here", score=0.7, step_id="1.2", step_title="Variables"),
            RetrievedChunk(text="there", score=0.8, step_id="3.1", step_title="Loops"),
        ]
        text = tutor_module._format_context(chunks, current_step_id="1.2")
        self.assertIn("الدرس الحالي 1.2: Variables", text)
        self.assertIn("درس آخر 3.1: Loops", text)
        self.assertLess(text.index("here"), text.index("there"))

# =====================================================================
# Phase 3: voice (Groq Whisper STT, edge-tts TTS)
# =====================================================================


class FakeHttpResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class VoiceServiceTests(unittest.TestCase):
    def setUp(self):
        from app.services import voice_service

        self.vs = voice_service

    def test_voice_is_picked_from_the_text_language(self):
        self.assertEqual(self.vs.pick_voice("المتغير هو صندوق في الذاكرة"), settings.TTS_VOICE_AR)
        self.assertEqual(self.vs.pick_voice("A variable stores a value"), settings.TTS_VOICE_EN)
        # Mostly Arabic with English terms still reads as Arabic.
        self.assertEqual(self.vs.pick_voice("في بايثون نستخدم print لطباعة القيم"), settings.TTS_VOICE_AR)
        self.assertEqual(self.vs.pick_voice("anything", language="ar"), settings.TTS_VOICE_AR)
        self.assertEqual(self.vs.pick_voice("أي شيء", language="en"), settings.TTS_VOICE_EN)

    def test_transcribe_sends_audio_to_groq_whisper(self):
        calls = []

        def fake_post(url, **kwargs):
            calls.append((url, kwargs))
            return FakeHttpResponse(200, {"text": " ما هو المتغير؟ ", "language": "arabic", "duration": 2.4})

        with mock.patch.object(self.vs, "http_post", fake_post), \
                mock.patch.object(settings, "GROQ_API_KEY", "test-key"):
            result = self.vs.transcribe(b"audio-bytes", "q.webm", "audio/webm", language="ar")

        self.assertEqual(
            result, {"text": "ما هو المتغير؟", "language": "arabic", "duration_seconds": 2.4, "rejected": None}
        )
        url, kwargs = calls[0]
        self.assertTrue(url.endswith("/audio/transcriptions"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["data"]["model"], settings.GROQ_STT_MODEL)
        self.assertEqual(kwargs["data"]["language"], "ar")
        self.assertEqual(kwargs["files"]["file"], ("q.webm", b"audio-bytes", "audio/webm"))

    def _transcribe_payload(self, payload):
        with mock.patch.object(self.vs, "http_post", return_value=FakeHttpResponse(200, payload)), \
                mock.patch.object(settings, "GROQ_API_KEY", "test-key"):
            return self.vs.transcribe(b"audio", "q.webm", "audio/webm")

    def test_silence_hallucinations_are_rejected(self):
        # Live: 3s of silence -> " Thank you.", room noise -> " so", a click -> " ."
        cases = [
            (" Thank you.", "English", -0.29),
            (" so", "English", -0.77),
            (" .", "English", -0.54),
            (" ترجمة نانسي قنقر", "Arabic", -0.3),
            ("", "English", -0.1),
        ]
        for text, language, logprob in cases:
            with self.subTest(text=text):
                result = self._transcribe_payload(
                    {"text": text, "language": language, "duration": 3.0,
                     "segments": [{"text": text, "avg_logprob": logprob, "no_speech_prob": 0.0}]}
                )
                self.assertEqual(result["text"], "")
                self.assertEqual(result["rejected"], "no_speech")

    def test_low_confidence_transcript_is_rejected(self):
        result = self._transcribe_payload(
            {"text": "variable lists maybe", "language": "English", "duration": 2.0,
             "segments": [{"text": "variable lists maybe", "avg_logprob": -0.9}]}
        )
        self.assertEqual((result["text"], result["rejected"]), ("", "low_confidence"))

    def test_languages_other_than_arabic_and_english_are_rejected(self):
        # Garbled questions came back tagged as another language.
        result = self._transcribe_payload(
            {"text": "これは何ですか", "language": "Japanese", "duration": 2.0,
             "segments": [{"text": "これは何ですか", "avg_logprob": -0.2}]}
        )
        self.assertEqual((result["text"], result["rejected"]), ("", "unsupported_language"))

    def test_confident_speech_is_kept(self):
        result = self._transcribe_payload(
            {"text": " ما هو المتغير في بيثون؟", "language": "Arabic", "duration": 4.3,
             "segments": [{"text": " ما هو المتغير في بيثون؟", "avg_logprob": -0.18, "no_speech_prob": 0.0}]}
        )
        self.assertEqual((result["text"], result["rejected"]), ("ما هو المتغير في بيثون؟", None))

    def test_transcribe_without_key_is_unavailable(self):
        with mock.patch.object(settings, "GROQ_API_KEY", ""):
            with self.assertRaises(self.vs.VoiceUnavailableError):
                self.vs.transcribe(b"x", "q.webm", "audio/webm")

    def test_transcribe_upstream_errors_are_unavailable_and_hide_details(self):
        for code in (401, 429, 500):
            with self.subTest(code=code):
                with mock.patch.object(self.vs, "http_post", return_value=FakeHttpResponse(code, {"error": "secret"})), \
                        mock.patch.object(settings, "GROQ_API_KEY", "test-key"), \
                        self.assertLogs("app.services.voice_service", level="WARNING"):
                    with self.assertRaises(self.vs.VoiceUnavailableError) as ctx:
                        self.vs.transcribe(b"x", "q.webm", "audio/webm")
                self.assertNotIn("secret", str(ctx.exception))

    def test_unreadable_audio_is_an_input_error_not_an_outage(self):
        # Live: Groq answers 400 invalid_media_file / unsupported type for bad files.
        body = {"error": {"message": "could not process file - is it a valid media file?", "code": "invalid_media_file"}}
        with mock.patch.object(self.vs, "http_post", return_value=FakeHttpResponse(400, body)), \
                mock.patch.object(settings, "GROQ_API_KEY", "test-key"), \
                self.assertLogs("app.services.voice_service", level="WARNING") as logs:
            with self.assertRaises(self.vs.VoiceInputError):
                self.vs.transcribe(b"x", "question.webm", "audio/webm")
        self.assertTrue(any("invalid_media_file" in line for line in logs.output))

    def test_upload_filename_comes_from_content_type(self):
        # Live: Groq rejects names without an audio extension ("q", "blob").
        cases = {
            "audio/webm;codecs=opus": "question.webm",
            "video/webm": "question.webm",
            "audio/ogg; codecs=opus": "question.ogg",
            "audio/mp4": "question.mp4",
            "audio/x-m4a": "question.m4a",
            "audio/mpeg": "question.mp3",
            "audio/wav": "question.wav",
            "audio/x-wav": "question.wav",
            "audio/flac": "question.flac",
        }
        for content_type, expected in cases.items():
            with self.subTest(content_type=content_type):
                self.assertEqual(self.vs.upload_filename(content_type, "blob"), expected)
        self.assertEqual(self.vs.upload_filename("audio/x-unknown", "clip.opus"), "question.opus")
        self.assertIsNone(self.vs.upload_filename("audio/x-unknown", "blob"))

    def test_transcribe_network_failure_is_unavailable(self):
        def boom(url, **kwargs):
            raise ConnectionError("down")

        with mock.patch.object(self.vs, "http_post", boom), mock.patch.object(settings, "GROQ_API_KEY", "k"), \
                self.assertLogs("app.services.voice_service", level="WARNING"):
            with self.assertRaises(self.vs.VoiceUnavailableError):
                self.vs.transcribe(b"x", "q.webm", "audio/webm")


class VoiceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        from app.services import voice_service

        self.vs = voice_service

    def _upload(self, data=b"audio", content_type="audio/webm", language=None):
        form = {"language": language} if language else {}
        return self.client.post(
            "/api/v1/voice/transcribe", files={"audio": ("q.webm", data, content_type)}, data=form
        )

    def test_routes_are_registered(self):
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("post", paths["/api/v1/voice/transcribe"])
        self.assertIn("post", paths["/api/v1/voice/speak"])

    def test_transcribe_returns_text(self):
        with mock.patch.object(self.vs, "transcribe", return_value={"text": "hi", "language": "english", "duration_seconds": 1.0, "rejected": None}) as t:
            response = self._upload(content_type="audio/webm;codecs=opus", language="en")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"text": "hi", "language": "english", "duration_seconds": 1.0, "rejected": None})
        self.assertEqual(t.call_args.kwargs["language"], "en")

    def test_transcribe_rejects_empty_large_and_non_audio_uploads(self):
        with mock.patch.object(self.vs, "transcribe") as t:
            self.assertEqual(self._upload(data=b"").status_code, 400)
            self.assertEqual(self._upload(data=b"x" * (settings.STT_MAX_BYTES + 1)).status_code, 413)
            self.assertEqual(self._upload(content_type="text/plain").status_code, 415)
            self.assertEqual(self._upload(language="fr-xx").status_code, 422)
        t.assert_not_called()

    def test_transcribe_sends_a_named_file_even_for_blob_uploads(self):
        with mock.patch.object(self.vs, "transcribe", return_value={"text": "hi", "language": "English", "duration_seconds": 1.0, "rejected": None}) as t:
            response = self.client.post(
                "/api/v1/voice/transcribe", files={"audio": ("blob", b"audio", "audio/ogg;codecs=opus")}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(t.call_args.args[1], "question.ogg")

    def test_transcribe_unknown_audio_type_without_extension_is_415(self):
        with mock.patch.object(self.vs, "transcribe") as t:
            response = self.client.post("/api/v1/voice/transcribe", files={"audio": ("blob", b"audio", "audio/x-unknown")})
        self.assertEqual(response.status_code, 415)
        t.assert_not_called()

    def test_unreadable_recording_maps_to_400(self):
        with mock.patch.object(self.vs, "transcribe", side_effect=self.vs.VoiceInputError("We couldn't read that recording")):
            response = self._upload()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "We couldn't read that recording")

    def test_transcribe_unavailable_maps_to_503(self):
        with mock.patch.object(self.vs, "transcribe", side_effect=self.vs.VoiceUnavailableError("Speech recognition is unavailable")):
            response = self._upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Speech recognition is unavailable")

    def test_speak_returns_mp3_with_chosen_voice(self):
        async def fake_synth(text, voice):
            return b"ID3-mp3-bytes"

        with mock.patch.object(self.vs, "synthesize", side_effect=fake_synth) as synth:
            response = self.client.post("/api/v1/voice/speak", json={"text": "المتغير صندوق"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "audio/mpeg")
        self.assertEqual(response.content, b"ID3-mp3-bytes")
        self.assertEqual(response.headers["x-voice"], settings.TTS_VOICE_AR)
        self.assertEqual(synth.call_args.args, ("المتغير صندوق", settings.TTS_VOICE_AR))

    def test_speak_validates_text(self):
        self.assertEqual(self.client.post("/api/v1/voice/speak", json={"text": "   "}).status_code, 422)
        too_long = "a" * (settings.TTS_MAX_CHARS + 1)
        self.assertEqual(self.client.post("/api/v1/voice/speak", json={"text": too_long}).status_code, 422)

    def test_speak_failure_maps_to_503(self):
        async def failing(text, voice):
            raise self.vs.VoiceUnavailableError("Voice playback is unavailable")

        with mock.patch.object(self.vs, "synthesize", side_effect=failing) as synth:
            response = self.client.post("/api/v1/voice/speak", json={"text": "hello"})
        self.assertEqual(response.status_code, 503)
        # Primary and fallback voice were both tried.
        self.assertEqual([c.args[1] for c in synth.call_args_list], [settings.TTS_VOICE_EN, settings.TTS_VOICE_EN_FALLBACK])

    def test_speak_falls_back_to_second_voice(self):
        # Live: ar-EG-ShakirNeural returned no audio for ordinary sentences.
        async def flaky(text, voice):
            if voice == settings.TTS_VOICE_AR:
                raise self.vs.VoiceUnavailableError("Voice playback is unavailable")
            return b"mp3"

        with mock.patch.object(self.vs, "synthesize", side_effect=flaky):
            response = self.client.post("/api/v1/voice/speak", json={"text": "المتغير صندوق"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-voice"], settings.TTS_VOICE_AR_FALLBACK)

    def test_voice_chain_puts_primary_first(self):
        self.assertEqual(self.vs.voice_chain("مرحبا بك"), [settings.TTS_VOICE_AR, settings.TTS_VOICE_AR_FALLBACK])
        self.assertEqual(self.vs.voice_chain("hello"), [settings.TTS_VOICE_EN, settings.TTS_VOICE_EN_FALLBACK])

    def test_voice_defaults(self):
        self.assertEqual(settings.GROQ_STT_MODEL, "whisper-large-v3-turbo")
        self.assertEqual(settings.TTS_VOICE_AR, "ar-EG-SalmaNeural")
        self.assertEqual(settings.TTS_VOICE_AR_FALLBACK, "ar-SA-HamedNeural")
        self.assertEqual(settings.TTS_VOICE_EN, "en-US-AndrewNeural")
        self.assertEqual(settings.TTS_VOICE_EN_FALLBACK, "en-US-AriaNeural")

# =====================================================================
# Phase 4: learner persistence, quota, explain-lesson
# =====================================================================

LEARNER = "learner-0001-test"
OTHER_LEARNER = "learner-0002-test"


def make_repo(path=":memory:"):
    from app.services.learner_store import SQLiteLearnerRepository

    return SQLiteLearnerRepository(path)


class LearnerRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def test_profile_round_trip_and_overwrite(self):
        self.assertIsNone(self.repo.get_profile(LEARNER))
        self.repo.save_profile(LEARNER, {"interests": ["Python"], "level": "beginner"})
        self.repo.save_profile(LEARNER, {"interests": ["Calculus"], "level": "advanced"})
        self.assertEqual(self.repo.get_profile(LEARNER), {"interests": ["Calculus"], "level": "advanced"})
        self.assertIsNone(self.repo.get_profile(OTHER_LEARNER))

    def test_lesson_completion_is_idempotent_and_per_course(self):
        self.repo.mark_lesson_complete(LEARNER, "Py", "1.1")
        self.repo.mark_lesson_complete(LEARNER, "Py", "1.1")
        self.repo.mark_lesson_complete(LEARNER, "Py", "1.2")
        self.repo.mark_lesson_complete(LEARNER, "Calc", "2.1")
        self.assertEqual(self.repo.completed_steps(LEARNER, "Py"), ["1.1", "1.2"])
        self.assertEqual(self.repo.all_completed(LEARNER), {"Calc": ["2.1"], "Py": ["1.1", "1.2"]})
        self.assertEqual(self.repo.completed_steps(OTHER_LEARNER, "Py"), [])

    def test_lesson_can_be_marked_incomplete(self):
        self.repo.mark_lesson_complete(LEARNER, "Py", "1.1")
        self.repo.mark_lesson_incomplete(LEARNER, "Py", "1.1")
        self.assertEqual(self.repo.completed_steps(LEARNER, "Py"), [])

    def test_question_counts_are_per_learner_and_day(self):
        self.assertEqual(self.repo.questions_used(LEARNER, "2026-11-23"), 0)
        self.assertEqual(self.repo.record_question(LEARNER, "2026-11-23"), 1)
        self.assertEqual(self.repo.record_question(LEARNER, "2026-11-23"), 2)
        self.assertEqual(self.repo.questions_used(LEARNER, "2026-11-24"), 0)
        self.assertEqual(self.repo.questions_used(OTHER_LEARNER, "2026-11-23"), 0)

    def test_data_survives_reopening_the_database(self):
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "nested", "codeu.db")
        first = make_repo(path)
        first.save_profile(LEARNER, {"interests": ["Python"]})
        first.mark_lesson_complete(LEARNER, "Py", "1.1")
        first.record_question(LEARNER, "2026-11-23")
        first.close()
        second = make_repo(path)
        self.addCleanup(second.close)
        self.assertEqual(second.get_profile(LEARNER), {"interests": ["Python"]})
        self.assertEqual(second.completed_steps(LEARNER, "Py"), ["1.1"])
        self.assertEqual(second.questions_used(LEARNER, "2026-11-23"), 1)


class QuotaTests(unittest.TestCase):
    def setUp(self):
        from app.services import quota

        self.quota = quota
        self.repo = make_repo()

    def test_status_counts_down_and_resets_at_utc_midnight(self):
        from datetime import datetime, timezone

        now = datetime(2026, 11, 23, 15, 30, tzinfo=timezone.utc)
        with mock.patch.object(settings, "DAILY_QUESTION_LIMIT", 3):
            self.repo.record_question(LEARNER, "2026-11-23")
            status = self.quota.quota_status(self.repo, LEARNER, now=now)
        self.assertEqual((status.limit, status.used, status.remaining), (3, 1, 2))
        self.assertEqual(status.resets_at, "2026-11-24T00:00:00+00:00")

    def test_zero_limit_means_unlimited(self):
        with mock.patch.object(settings, "DAILY_QUESTION_LIMIT", 0):
            for _ in range(5):
                self.repo.record_question(LEARNER, self.quota.utc_day())
            status = self.quota.quota_status(self.repo, LEARNER)
        self.assertIsNone(status.limit)
        self.assertIsNone(status.remaining)

    def test_default_limit_matches_freemium_design(self):
        self.assertEqual(settings.DAILY_QUESTION_LIMIT, 3)


class LearnerApiBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        import tempfile

        from app.services.learner_store import get_learner_repository

        self.repo = make_repo()
        app.dependency_overrides[get_learner_repository] = lambda: self.repo
        self.addCleanup(app.dependency_overrides.clear)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.courses_dir = tmp.name
        write_course(tmp.name, "Py_Course", make_roadmap_dict(title="Py Course"), manifest={"status": "complete"})
        for name, value in (("GENERATED_COURSES_DIR", tmp.name), ("DATA_DIR", Path(tmp.name) / "data")):
            patcher = mock.patch.object(settings, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def headers(self, learner=LEARNER):
        return {"X-Learner-Id": learner}


class LearnerApiTests(LearnerApiBase):
    def test_learner_id_header_is_required_and_validated(self):
        self.assertEqual(self.client.get("/api/v1/learners/me/quota").status_code, 400)
        for bad in ("short", "has spaces in it", "x" * 65, "../../etc/passwd"):
            with self.subTest(bad=bad):
                response = self.client.get("/api/v1/learners/me/quota", headers={"X-Learner-Id": bad})
                self.assertEqual(response.status_code, 400)

    def test_profile_put_then_get(self):
        self.assertEqual(self.client.get("/api/v1/learners/me/profile", headers=self.headers()).status_code, 404)
        profile = {"interests": ["Python", "python", "Calculus"], "level": "beginner", "background": "student"}
        response = self.client.put("/api/v1/learners/me/profile", json=profile, headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["interests"], ["Python", "Calculus"])  # schema dedupes
        stored = self.client.get("/api/v1/learners/me/profile", headers=self.headers()).json()
        self.assertEqual(stored["level"], "beginner")
        self.assertEqual(self.client.get("/api/v1/learners/me/profile", headers=self.headers(OTHER_LEARNER)).status_code, 404)

    def test_profile_validation(self):
        response = self.client.put("/api/v1/learners/me/profile", json={"interests": [], "level": "beginner"}, headers=self.headers())
        self.assertEqual(response.status_code, 422)

    def test_completing_lessons_reports_progress(self):
        url = "/api/v1/learners/me/progress/Py_Course/lessons/1.1/complete"
        first = self.client.post(url, headers=self.headers())
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {"course_id": "Py_Course", "completed_steps": ["1.1"], "total_lessons": 8, "percent": 12})
        self.client.post("/api/v1/learners/me/progress/Py_Course/lessons/1.2/complete", headers=self.headers())
        progress = self.client.get("/api/v1/learners/me/progress/Py_Course", headers=self.headers()).json()
        self.assertEqual((progress["completed_steps"], progress["percent"]), (["1.1", "1.2"], 25))
        overview = self.client.get("/api/v1/learners/me/progress", headers=self.headers()).json()
        self.assertEqual([c["course_id"] for c in overview], ["Py_Course"])

    def test_lesson_can_be_unmarked(self):
        url = "/api/v1/learners/me/progress/Py_Course/lessons/1.1/complete"
        self.client.post(url, headers=self.headers())
        response = self.client.delete(url, headers=self.headers())
        self.assertEqual(response.json()["completed_steps"], [])

    def test_unknown_course_or_lesson_is_404(self):
        for url in ("/api/v1/learners/me/progress/Nope/lessons/1.1/complete",
                    "/api/v1/learners/me/progress/Py_Course/lessons/9.9/complete"):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, headers=self.headers()).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/learners/me/progress/Nope", headers=self.headers()).status_code, 404)

    def test_progress_ignores_steps_no_longer_in_the_course(self):
        self.repo.mark_lesson_complete(LEARNER, "Py_Course", "1.1")
        self.repo.mark_lesson_complete(LEARNER, "Py_Course", "old-step")
        progress = self.client.get("/api/v1/learners/me/progress/Py_Course", headers=self.headers()).json()
        self.assertEqual(progress["completed_steps"], ["1.1"])

    def test_quota_endpoint(self):
        with mock.patch.object(settings, "DAILY_QUESTION_LIMIT", 3):
            response = self.client.get("/api/v1/learners/me/quota", headers=self.headers())
        body = response.json()
        self.assertEqual((body["limit"], body["used"], body["remaining"]), (3, 0, 3))


class RaiseHandQuotaTests(LearnerApiBase):
    def setUp(self):
        super().setUp()
        self.gemini = FakeGeminiClient()
        for target, name, value in (
            (gemini_service, "get_gemini_client", mock.Mock(return_value=self.gemini)),
            (tutor_module, "search_course_rag", mock.Mock(return_value=[RetrievedChunk(text="ctx", score=0.8, step_id="1.1", step_title="T")])),
            (settings, "DAILY_QUESTION_LIMIT", 3),
        ):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def ask(self, headers=None):
        return self.client.post(
            "/api/v1/tutor/raise-hand",
            json={"course_title": "Py Course", "step_id": "1.1", "student_question": "What is x?"},
            headers=headers or {},
        )

    def test_three_questions_then_429(self):
        remaining = [self.ask(self.headers()).json()["questions_remaining"] for _ in range(3)]
        self.assertEqual(remaining, [2, 1, 0])
        blocked = self.ask(self.headers())
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("3", blocked.json()["detail"])
        self.assertEqual(len(self.gemini.models.calls), 3)  # no generation when blocked

    def test_failed_answers_do_not_use_quota(self):
        tutor_module.search_course_rag.side_effect = RagUnavailableError("down")
        self.assertEqual(self.ask(self.headers()).status_code, 503)
        self.assertEqual(self.repo.questions_used(LEARNER, __import__("app.services.quota", fromlist=["x"]).utc_day()), 0)

    def test_quota_is_per_learner(self):
        for _ in range(3):
            self.ask(self.headers())
        self.assertEqual(self.ask(self.headers(OTHER_LEARNER)).status_code, 200)

    def test_requests_without_learner_id_are_not_counted(self):
        for _ in range(4):
            response = self.ask()
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json()["questions_remaining"])

    def test_invalid_learner_id_is_rejected(self):
        self.assertEqual(self.ask({"X-Learner-Id": "bad id"}).status_code, 400)


class ExplainLessonTests(LearnerApiBase):
    def setUp(self):
        super().setUp()
        self.gemini = FakeGeminiClient()
        self.script = "في هذا الدرس نتعلم **المتغيرات**. المتغير اسم يشير إلى قيمة."
        self.gemini.models.generate_content = mock.Mock(return_value=pytypes.SimpleNamespace(text=self.script))
        patcher = mock.patch.object(gemini_service, "get_gemini_client", return_value=self.gemini)
        patcher.start()
        self.addCleanup(patcher.stop)

    def explain(self, course="Py Course", step="1.1"):
        return self.client.post("/api/v1/tutor/explain-lesson", json={"course_title": course, "step_id": step})

    def test_returns_a_plain_spoken_script_grounded_in_the_lesson(self):
        response = self.explain()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body["course_id"], body["step_id"], body["title"]), ("Py_Course", "1.1", "Setup 1.1"))
        self.assertEqual(body["script"], "في هذا الدرس نتعلم المتغيرات. المتغير اسم يشير إلى قيمة.")
        self.assertFalse(body["cached"])
        call = self.gemini.models.generate_content.call_args.kwargs
        self.assertIn("Body 1.1", call["contents"])  # the lesson text is the source
        self.assertNotIn("## Setup 1.1", call["contents"])  # saved header stripped
        system = call["config"].system_instruction
        self.assertIn("نص الدرس", system)
        self.assertEqual(call["model"], settings.GEMINI_MODEL_NAME)

    def test_second_request_is_served_from_cache(self):
        self.explain()
        again = self.explain().json()
        self.assertTrue(again["cached"])
        self.assertEqual(self.gemini.models.generate_content.call_count, 1)

    def test_cache_is_invalidated_when_the_lesson_changes(self):
        from app.core.course_paths import lesson_filename

        self.explain()
        path = os.path.join(self.courses_dir, "Py_Course", lesson_filename("1.1", "Setup 1.1"))
        with open(path, "a", encoding="utf-8") as f:
            f.write("\nNew paragraph")
        self.assertFalse(self.explain().json()["cached"])
        self.assertEqual(self.gemini.models.generate_content.call_count, 2)

    def test_snake_case_names_survive_cleanup(self):
        from app.services.lecture_service import to_spoken_text

        self.assertEqual(to_spoken_text("نستخدم my_var_name و **مهم**"), "نستخدم my_var_name و مهم")

    def test_long_scripts_are_cut_at_a_sentence(self):
        sentence = "هذه جملة شرح طويلة. "
        self.gemini.models.generate_content.return_value = pytypes.SimpleNamespace(text=sentence * 400)
        script = self.explain().json()["script"]
        self.assertLessEqual(len(script), settings.LECTURE_MAX_CHARS)
        self.assertTrue(script.endswith("."))

    def test_unknown_course_or_lesson_is_404(self):
        self.assertEqual(self.explain(course="Nope").status_code, 404)
        self.assertEqual(self.explain(step="9.9").status_code, 404)

    def test_empty_or_refused_generation_is_502(self):
        for text in ("", "NOT_IN_CONTEXT"):
            with self.subTest(text=text):
                self.gemini.models.generate_content.return_value = pytypes.SimpleNamespace(text=text)
                self.gemini.models.generate_content.side_effect = None
                with self.assertLogs("app.services.lecture_service", level="WARNING"):
                    response = self.client.post(
                        "/api/v1/tutor/explain-lesson", json={"course_title": "Py Course", "step_id": "1.2"}
                    )
                self.assertEqual(response.status_code, 502)

    def test_model_failure_is_502(self):
        self.gemini.models.generate_content.side_effect = ValueError("secret detail")
        with self.assertLogs(level="ERROR"):
            response = self.explain(step="1.3")
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret", response.text)

    def test_explaining_does_not_use_question_quota(self):
        with mock.patch.object(settings, "DAILY_QUESTION_LIMIT", 1):
            self.client.post("/api/v1/tutor/explain-lesson", json={"course_title": "Py Course", "step_id": "1.1"}, headers=self.headers())
        self.assertEqual(self.repo.questions_used(LEARNER, __import__("app.services.quota", fromlist=["x"]).utc_day()), 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
