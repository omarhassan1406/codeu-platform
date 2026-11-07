"""Integration and smoke tests for the CodeU-Backend API.

Run from the repository root:
    ./venv/Scripts/python.exe test_backend.py

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
_ai_clients_stub.embedding_model = _ExternalServiceGuard()
_ai_clients_stub.qdrant_client = _ExternalServiceGuard()
_ai_clients_stub.gemini_client = FakeGeminiClient()
sys.modules["app.services.ai_clients"] = _ai_clients_stub

from fastapi.testclient import TestClient

import Generate_Course
from app.api.v1.endpoints import tutor as tutor_module
from app.core.config import settings
from app.main import app
from app.services import gemini_service


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
        cls.original_pipeline = Generate_Course.run_codeu_complete_pipeline

    def setUp(self):
        self.pipeline_calls = []
        self.pipeline_done = threading.Event()

        def fake_pipeline(course_topic):
            self.pipeline_calls.append(course_topic)
            self.pipeline_done.set()

        Generate_Course.run_codeu_complete_pipeline = fake_pipeline

    def tearDown(self):
        Generate_Course.run_codeu_complete_pipeline = self.original_pipeline

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
        def failing_pipeline(course_topic):
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
        gemini_service.gemini_client = self.gemini
        self.rag_context = []
        self.rag_calls = []

        def fake_rag(course_title, student_question, limit=3):
            self.rag_calls.append(
                {
                    "course_title": course_title,
                    "student_question": student_question,
                    "limit": limit,
                }
            )
            return self.rag_context

        self.rag_patcher = mock.patch.object(tutor_module, "search_course_rag", side_effect=fake_rag)
        self.rag_patcher.start()

    def tearDown(self):
        self.rag_patcher.stop()

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
                    "limit": 3,
                }
            ],
        )

        call = self.gemini.models.calls[0]
        self.assertEqual(call["model"], settings.GEMINI_MODEL_NAME)
        self.assertIn("chunk-1", call["contents"])
        self.assertIn("What is a variable?", call["contents"])
        self.assertIn("السياق", call["config"].system_instruction)

    def test_raise_hand_falls_back_on_rate_limit(self):
        self.rag_context = ["chunk-1"]
        self.gemini.models.failures = {
            settings.GEMINI_MODEL_NAME: make_rate_limit_error(settings.GEMINI_MODEL_NAME)
        }

        with self.assertLogs("app.services.gemini_service", level="WARNING") as captured:
            response = self._post_question()

        self.assertEqual(response.status_code, 200)
        fallback_model = settings.GEMINI_MODEL_HIERARCHY[0]
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


class CourseGeneratorServiceTests(unittest.TestCase):
    ROADMAP_JSON = (
        '{"course_title": "Test Course", "target_audience": "Beginners", '
        '"sections": [{"section_id": 1, "section_title": "Basics", "description": "Intro", '
        '"steps": [{"step_id": "1.1", "step_title": "Setup", "duration_mins": 10, '
        '"learning_objectives": ["Install Python"]}]}]}'
    )

    def test_roadmap_generation_uses_fallback_wrapper_and_course_model(self):
        captured = {}

        def fake_generation(*, contents, config=None, preferred_model=None):
            captured["preferred_model"] = preferred_model
            captured["config"] = config
            return pytypes.SimpleNamespace(text=self.ROADMAP_JSON)

        with mock.patch.object(
            Generate_Course, "generate_content_with_fallback", side_effect=fake_generation
        ):
            roadmap = Generate_Course.generate_course_roadmap("Python")

        self.assertEqual(captured["preferred_model"], settings.GEMINI_COURSE_MODEL)
        self.assertIs(captured["config"].response_schema, Generate_Course.CourseRoadmap)
        self.assertEqual(captured["config"].response_mime_type, "application/json")
        self.assertEqual(roadmap.course_title, "Test Course")
        self.assertEqual(roadmap.sections[0].steps[0].step_id, "1.1")

    def test_step_content_generation_uses_fallback_wrapper_and_course_model(self):
        captured = {}

        def fake_generation(*, contents, config=None, preferred_model=None):
            captured["preferred_model"] = preferred_model
            captured["config"] = config
            captured["contents"] = contents
            return pytypes.SimpleNamespace(text="# Lesson content")

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
        self.assertEqual(content, "# Lesson content")


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
        self.original_client = gemini_service.gemini_client
        self.gemini = FakeGeminiClient()
        gemini_service.gemini_client = self.gemini

    def tearDown(self):
        gemini_service.gemini_client = self.original_client

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
