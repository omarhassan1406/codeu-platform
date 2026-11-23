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

        def fake_pipeline(course_topic):
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
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].id, Generate_Course.make_point_id("Py", "1.1", 0))

    def test_ingestion_failure_is_raised_after_retries(self):
        qdrant = mock.Mock()
        qdrant.upsert.side_effect = ConnectionError("down")
        with mock.patch.object(Generate_Course, "get_qdrant_client", return_value=qdrant), \
             mock.patch.object(Generate_Course, "get_embedding_model", return_value=FakeEmbedding()), \
             mock.patch.object(Generate_Course.time, "sleep"):
            with self.assertRaises(Generate_Course.IngestionError):
                Generate_Course.ingest_lesson_to_qdrant_with_retry("Py", "Basics", "1.1", "Setup", "text")
        self.assertEqual(qdrant.upsert.call_count, 3)

if __name__ == "__main__":
    unittest.main(verbosity=2)
