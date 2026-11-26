"""AI features with a fake model: free-text proposals (US 2.41) and grounded price estimates."""

import io
import json
import urllib.error
from decimal import Decimal
from uuid import uuid4

import pytest

from modules.quotations.application.estimators import (
    AiPriceEstimator,
    FallbackPriceEstimator,
    StatisticalPriceEstimator,
)
from modules.quotations.application.item_proposals import ItemProposer, strip_personal_data
from modules.quotations.domain.pricing import PriceEstimate, PriceSource
from modules.quotations.infrastructure.pricing.cached_estimator import CachedPriceEstimator
from modules.quotations.ports.outbound.ports import PriceEstimator
from modules.shared_kernel.domain.exceptions import ServiceUnavailableError, ValidationError
from modules.shared_kernel.domain.money import PriceRange
from modules.shared_kernel.infrastructure.llm.openai_compatible import (
    OpenAICompatibleLanguageModel,
    parse_json_object,
)
from modules.shared_kernel.ports.outbound.language_model import LanguageModelError

from .fakes import BOARD, CHAIR, DESK, BrokenEstimator, FakeCatalog, FakeLanguageModel, FixedHistory


def ai_estimator(answer=None, **model_options):
    model = FakeLanguageModel(answer, **model_options)
    return AiPriceEstimator(model, FixedHistory(), FakeCatalog()), model


def estimate_for(code, low, high, based_on=("SIL-001",)):
    return {"code": code, "min_unit_price": low, "max_unit_price": high, "based_on": list(based_on)}


# --- Price estimates -----------------------------------------------------------------------------


def test_ai_estimate_is_accepted_only_when_grounded_in_real_references():
    estimator, model = ai_estimator(
        {
            "estimates": [
                estimate_for("MES-002", 300000, 360000),  # cites the chair reference: accepted
                estimate_for("TAB-003", 500000, 600000, based_on=["XXX-999"]),  # unknown reference
            ]
        }
    )

    result = estimator.estimate([(DESK.id, 10), (BOARD.id, 1)])

    assert result == {
        DESK.id: PriceEstimate(PriceRange(Decimal(300000), Decimal(360000)), PriceSource.AI)
    }
    sent = json.loads(model.prompts[0])
    assert sent["reference_prices"][0] == {
        "code": "SIL-001",
        "description": "Silla escolar",
        "unit": "Unidad",
        "quantity": 40,
        "unit_price": 180000,
    }


@pytest.mark.parametrize(
    "entry",
    [
        estimate_for("MES-002", 10, 20),  # far below the references: invented
        estimate_for("MES-002", 300000, 9000000),  # far above
        estimate_for("MES-002", 500, 100),  # min > max
        estimate_for("MES-002", "mucho", 100),
        estimate_for("MES-002", 300000, 360000, based_on=[]),  # no reference cited
    ],
)
def test_ai_estimates_that_look_invented_are_discarded(entry):
    estimator, _ = ai_estimator({"estimates": [entry]})
    assert estimator.estimate([(DESK.id, 10)]) == {}


def test_no_ai_call_without_references_or_without_provider():
    class NoHistory(FixedHistory):
        def reference_samples(self, since, limit):
            return []

    model = FakeLanguageModel({"estimates": [estimate_for("MES-002", 1, 2)]})
    assert AiPriceEstimator(model, NoHistory(), FakeCatalog()).estimate([(DESK.id, 1)]) == {}
    assert model.prompts == []  # never invents a price without reference data

    estimator, model = ai_estimator(available=False)
    assert estimator.estimate([(DESK.id, 1)]) == {} and model.prompts == []


def test_fallback_uses_own_history_first_and_ai_only_for_the_gaps():
    ai, model = ai_estimator({"estimates": [estimate_for("MES-002", 300000, 360000)]})
    chain = FallbackPriceEstimator([StatisticalPriceEstimator(FixedHistory()), ai])

    result = chain.estimate([(CHAIR.id, 40), (DESK.id, 10)])

    assert result[CHAIR.id].source is PriceSource.HISTORY
    assert result[DESK.id].source is PriceSource.AI
    asked = [p["code"] for p in json.loads(model.prompts[0])["products_to_estimate"]]
    assert asked == ["MES-002"]  # one call, only for the product without history


def test_a_failing_ai_never_breaks_the_estimate():
    chain = FallbackPriceEstimator([StatisticalPriceEstimator(FixedHistory()), BrokenEstimator()])
    result = chain.estimate([(CHAIR.id, 1), (DESK.id, 1)])
    assert set(result) == {CHAIR.id}


def test_cached_estimator_asks_once_per_product():
    class Counting(PriceEstimator):
        calls: list = []

        def estimate(self, requests):
            self.calls.append([pid for pid, _ in requests])
            return {CHAIR.id: PriceEstimate(PriceRange(1, 2), PriceSource.AI)}

    inner = Counting()
    cached = CachedPriceEstimator(inner, 60, prefix=f"test-{uuid4()}")

    first = cached.estimate([(CHAIR.id, 1), (DESK.id, 1)])
    second = cached.estimate([(CHAIR.id, 5), (DESK.id, 5)])

    assert first == second == {CHAIR.id: PriceEstimate(PriceRange(1, 2), PriceSource.AI)}
    assert inner.calls == [[CHAIR.id, DESK.id]]  # "no estimate" is cached too


# --- Free text → products ------------------------------------------------------------------------


def test_proposal_keeps_only_catalog_products_and_merges_repeats():
    model = FakeLanguageModel(
        {
            "items": [
                {"code": "sil-001", "quantity": 70},
                {"code": "SIL-001", "quantity": 35},
                {"code": "MES-002", "quantity": "x"},
                {"code": "PUP-404", "quantity": 1},
            ],
            "unavailable": ["Pupitres metálicos"],
        }
    )
    proposal = ItemProposer(model, FakeCatalog()).propose(
        "Sillas para 3 salones de 35 estudiantes, mesas y pupitres metálicos"
    )

    assert [(line.product.code, line.quantity) for line in proposal.lines] == [
        ("SIL-001", 105),
        ("MES-002", 1),
    ]
    assert proposal.unavailable == ("PUP-404", "Pupitres metálicos")


def test_personal_data_is_removed_before_calling_the_ai():
    model = FakeLanguageModel({"items": []})
    ItemProposer(model, FakeCatalog()).propose(
        "Soy Laura, laura@colegio.edu.co, cel 310 456 7890, NIT 900.456.789-1: necesito 20 sillas"
    )

    sent = json.loads(model.prompts[0])["customer_request"]
    assert "laura@colegio.edu.co" not in sent and "310 456 7890" not in sent
    assert "900.456.789-1" not in sent and "20 sillas" in sent
    assert strip_personal_data("3 salones de 35") == "3 salones de 35"  # short numbers stay


def test_proposal_errors():
    with pytest.raises(ValidationError):
        ItemProposer(FakeLanguageModel(), FakeCatalog()).propose("sillas")
    with pytest.raises(ServiceUnavailableError) as error:
        ItemProposer(FakeLanguageModel(error=True), FakeCatalog()).propose("Necesito 20 sillas")
    assert error.value.code == "AI_UNAVAILABLE"
    with pytest.raises(ServiceUnavailableError):
        ItemProposer(FakeLanguageModel(available=False), FakeCatalog()).propose("Necesito sillas")


# --- OpenAI-compatible adapter -------------------------------------------------------------------


def test_parse_json_object_tolerates_fences_and_text():
    assert parse_json_object('```json\n{"items": []}\n```') == {"items": []}
    assert parse_json_object('Claro: {"a": 1} ¡listo!') == {"a": 1}
    with pytest.raises(LanguageModelError):
        parse_json_object("no hay JSON")


def test_adapter_sends_the_key_only_in_the_header(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"], seen["headers"] = request.full_url, dict(request.header_items())
        seen["body"] = json.loads(request.data)
        content = json.dumps({"choices": [{"message": {"content": '{"ok": true}'}}]})
        return io.BytesIO(content.encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    model = OpenAICompatibleLanguageModel("https://llm.test/api/v1/", "test-key", "some/model")

    assert model.complete_json("system", "user") == {"ok": True}
    assert seen["url"] == "https://llm.test/api/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["headers"]["User-agent"].startswith("IMSI/")  # not "Python-urllib" (blocked)
    assert seen["body"]["model"] == "some/model" and "test-key" not in json.dumps(seen["body"])


def test_session_header_is_sent_only_when_configured(monkeypatch):
    sent = []

    def fake_urlopen(request, timeout):
        sent.append({k.lower(): v for k, v in request.header_items()})
        content = json.dumps({"choices": [{"message": {"content": "{}"}}]})
        return io.BytesIO(content.encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    go = OpenAICompatibleLanguageModel(
        "https://llm.test", "k", "m", session_header="x-opencode-session"
    )
    go.complete_json("s", "u")
    go.complete_json("s", "u")
    OpenAICompatibleLanguageModel("https://llm.test", "k", "m").complete_json("s", "u")

    first, second, plain = (h.get("x-opencode-session") for h in sent)
    assert first.startswith("ses_") and second.startswith("ses_") and first != second
    assert plain is None  # other providers never receive it


def test_adapter_errors_log_the_provider_reason(monkeypatch, caplog):
    def failing(request, timeout):
        body = io.BytesIO(b'{"error": {"message": "No endpoints found", "code": 404}}')
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, body)

    monkeypatch.setattr("urllib.request.urlopen", failing)
    with pytest.raises(LanguageModelError):
        OpenAICompatibleLanguageModel("https://llm.test", "k", "m").complete_json("s", "u")
    assert "HTTP 404: No endpoints found" in caplog.text

    def firewall(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", {}, io.BytesIO(b"error code: 1010")
        )

    monkeypatch.setattr("urllib.request.urlopen", firewall)
    with pytest.raises(LanguageModelError):
        OpenAICompatibleLanguageModel("https://llm.test", "k", "m").complete_json("s", "u")
    assert "HTTP 403: error code: 1010" in caplog.text

    def reset(request, timeout):
        raise ConnectionResetError("connection reset by peer")

    monkeypatch.setattr("urllib.request.urlopen", reset)
    with pytest.raises(LanguageModelError):  # not a 500: the provider dropped the connection
        OpenAICompatibleLanguageModel("https://llm.test", "k", "m").complete_json("s", "u")

    with pytest.raises(LanguageModelError):  # no key configured
        OpenAICompatibleLanguageModel("https://llm.test", "", "m").complete_json("s", "u")
