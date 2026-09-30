# -*- coding: utf-8 -*-

"""The Model Chemistry parameters' rule: the model chemistry must be offered by an
installed program (the basis is a free choice), as the step checks when it runs."""

import pytest

import model_chemistry_step
from model_chemistry_step import model_chemistry as mc

OFFERED = {
    "ORCA:DFT@B3LYP/def2-SVP": {
        "level": "ORCA:DFT@B3LYP/def2-SVP",
        "owner": "ORCA",
        "type": "DFT",
        "method": "B3LYP",
        "basis": "def2-SVP",
        "cutoff": None,
        "step": "ORCA",
        "options": {},
    }
}


@pytest.fixture
def parameters(monkeypatch):
    monkeypatch.setattr(mc, "discover_model_chemistries", lambda **kw: OFFERED)
    model_chemistry_step.ModelChemistryParameters._available = {}
    yield model_chemistry_step.ModelChemistryParameters()
    model_chemistry_step.ModelChemistryParameters._available = {}


@pytest.mark.parametrize(
    "selected",
    ["ORCA:DFT@B3LYP/def2-SVP", "ORCA:DFT@B3LYP/bse:cc-pVTZ", "$model", ""],
)
def test_available(parameters, selected):
    values = {**parameters.current_values(), "model_chemistry": selected}
    assert parameters.problems(values) == []


def test_not_available(parameters):
    values = {**parameters.current_values(), "model_chemistry": "ORCA:DFT@NOPE/x"}
    (problem,) = parameters.problems(values)
    assert "'ORCA:DFT@NOPE/x' is not available" in problem
    assert "ORCA:DFT@B3LYP/def2-SVP" in problem
