#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the model-chemistry grammar (parse / compose)."""

import pytest

from model_chemistry_step.grammar import (
    parse_model_chemistry,
    compose_model_chemistry,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "MOPAC:SQM@PM6-ORG",
            {
                "program": "MOPAC",
                "type": "SQM",
                "method": "PM6-ORG",
                "basis": None,
                "cutoff": None,
            },
        ),
        (
            "Psi4:DFT@B3LYP/def2-SVP",
            {
                "program": "Psi4",
                "type": "DFT",
                "method": "B3LYP",
                "basis": "def2-SVP",
                "cutoff": None,
            },
        ),
        (
            "VASP:DFT@PBE/PAW@500eV",
            {
                "program": "VASP",
                "type": "DFT",
                "method": "PBE",
                "basis": "PAW",
                "cutoff": "500eV",
            },
        ),
    ],
)
def test_parse(text, expected):
    """Each component is parsed out correctly."""
    parsed = parse_model_chemistry(text)
    for key, value in expected.items():
        assert parsed[key] == value
    assert parsed["model_chemistry"] == text


@pytest.mark.parametrize(
    "text",
    [
        "MOPAC:SQM@PM6-ORG",
        "Psi4:DFT@B3LYP/def2-SVP",
        "VASP:DFT@PBE/PAW@500eV",
    ],
)
def test_round_trip(text):
    """compose(parse(text)) reproduces the original string."""
    assert compose_model_chemistry(parse_model_chemistry(text)) == text


@pytest.mark.parametrize(
    "text",
    [
        "PM6-ORG",  # no ':' and no '@'
        "MOPAC-SQM-PM6",  # no ':'
        "MOPAC:SQM",  # ':' but no '@'
    ],
)
def test_parse_rejects_malformed(text):
    """Strings missing required delimiters raise ValueError."""
    with pytest.raises(ValueError):
        parse_model_chemistry(text)


def test_compose_rejects_cutoff_without_basis():
    """A cutoff without a basis is not expressible in the grammar."""
    with pytest.raises(ValueError):
        compose_model_chemistry(
            {
                "program": "VASP",
                "type": "DFT",
                "method": "PBE",
                "cutoff": "500eV",
            }
        )


def test_compose_rejects_missing_component():
    """Missing a required component raises ValueError."""
    with pytest.raises(ValueError):
        compose_model_chemistry({"program": "MOPAC", "type": "SQM"})
