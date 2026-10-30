"""Checks that run without calling Gemma: the risk score, the number check and the approval queue."""

import pytest

from floodsense import alerts
from floodsense.agent import draft_alert, rank_wards, ward_details
from floodsense.alerts import check_alert, numbers_in
from floodsense.wards import find_ward, load_wards


@pytest.fixture(autouse=True)
def temp_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(alerts, "QUEUE", tmp_path / "alerts.json")


# Normal cases

def test_wards_ranked_highest_risk_first():
    scores = load_wards()["risk_score"].tolist()
    assert scores == sorted(scores, reverse=True)
    assert rank_wards(1)["wards"][0]["ward"] == "Bunyala South"


def test_good_alert_is_saved_as_pending():
    text = "TAHADHARI Bunyala South: watu 11,300 hatarini. Hamia sehemu za juu sasa. Msaada: 1199"
    out = draft_alert("Bunyala South", "sw", text)
    assert out["saved"] and out["status"] == "pending approval"
    assert alerts.list_alerts("pending")[0]["text"] == text


def test_approve_moves_alert_out_of_pending():
    out = draft_alert("Bunyala West", "en", "FLOOD ALERT Bunyala West: 7,500 people at risk. Help: 1199")
    alerts.set_status(out["id"], "approved")
    assert alerts.list_alerts("pending") == []
    assert alerts.list_alerts("approved")[0]["id"] == out["id"]


# Edge cases

def test_short_ward_name_matches():
    assert find_ward("south")["ward"] == "Bunyala South"


def test_units_are_not_counted_as_numbers():
    assert numbers_in("41 km2 flooded, 11,300 people. Help: 1199") == [41, 11300, 1199]


def test_alert_over_160_characters_is_rejected():
    assert any("Too long" in p for p in check_alert("x" * 161, find_ward("Bunyala North")))


# Failure cases

def test_invented_number_is_rejected():
    out = draft_alert("Bunyala South", "en", "FLOOD ALERT Bunyala South: 50,000 people at risk.")
    assert out["rejected"] and "50000" in out["problems"][0]
    assert alerts.list_alerts("pending") == []


def test_unknown_place_returns_error_not_numbers():
    out = ward_details("Port Victoria town")
    assert "error" in out and "Bunyala South" in out["error"]
