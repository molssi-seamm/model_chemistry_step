#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the model-chemistry grammar (task|level form)."""

import pytest

from model_chemistry_step.grammar import (
    parse_level,
    parse_model_chemistry,
    compose_model_chemistry,
    comparability_key,
)


# ---------------------------------------------------------------------------
# parse_level -- the bare [owner:]type@method[/basis[@cutoff]] spec
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "SQM@PM6-ORG",
            {
                "owner": None,
                "type": "SQM",
                "method": "PM6-ORG",
                "basis": None,
                "cutoff": None,
            },
        ),
        (
            "MOPAC:SQM@PM6-ORG",
            {
                "owner": "MOPAC",
                "type": "SQM",
                "method": "PM6-ORG",
                "basis": None,
                "cutoff": None,
            },
        ),
        (
            "DFT@PBE/PAW@500eV",
            {
                "owner": None,
                "type": "DFT",
                "method": "PBE",
                "basis": "PAW",
                "cutoff": "500eV",
            },
        ),
    ],
)
def test_parse_level(text, expected):
    parsed = parse_level(text)
    for key, value in expected.items():
        assert parsed[key] == value
    assert parsed["level"] == text


def test_parse_level_rejects_missing_at():
    with pytest.raises(ValueError):
        parse_level("MOPAC:SQM")


# ---------------------------------------------------------------------------
# parse_model_chemistry -- the full driver:task|level string
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "MOPAC:OPT|SQM@PM6-ORG",
            {
                "driver": "MOPAC",
                "task": "OPT",
                "owner": None,
                "type": "SQM",
                "method": "PM6-ORG",
                "basis": None,
                "cutoff": None,
            },
        ),
        (
            "LAMMPS:MD|VFF@OPLS-AA",
            {
                "driver": "LAMMPS",
                "task": "MD",
                "owner": None,
                "type": "VFF",
                "method": "OPLS-AA",
                "basis": None,
                "cutoff": None,
            },
        ),
        (
            "LAMMPS:MD|MOPAC:SQM@PM6-ORG",
            {
                "driver": "LAMMPS",
                "task": "MD",
                "owner": "MOPAC",
                "type": "SQM",
                "method": "PM6-ORG",
                "basis": None,
                "cutoff": None,
            },
        ),
        (
            "VASP:OPT|DFT@PBE/PAW@500eV",
            {
                "driver": "VASP",
                "task": "OPT",
                "owner": None,
                "type": "DFT",
                "method": "PBE",
                "basis": "PAW",
                "cutoff": "500eV",
            },
        ),
    ],
)
def test_parse_model_chemistry(text, expected):
    parsed = parse_model_chemistry(text)
    for key, value in expected.items():
        assert parsed[key] == value
    assert parsed["geometry"] is None


def test_parse_compound():
    text = "Psi4:SP|QC@CCSD(T)/cc-pVTZ//Psi4:OPT|DFT@B3LYP/def2-SVP"
    parsed = parse_model_chemistry(text)
    assert parsed["task"] == "SP"
    assert parsed["type"] == "QC"
    assert parsed["method"] == "CCSD(T)"
    assert parsed["basis"] == "cc-pVTZ"
    geom = parsed["geometry"]
    assert geom is not None
    assert geom["task"] == "OPT"
    assert geom["method"] == "B3LYP"
    assert geom["basis"] == "def2-SVP"
    assert geom["geometry"] is None


@pytest.mark.parametrize(
    "text",
    [
        "SQM@PM6-ORG",  # no '|' (a bare level, not a full string)
        "MD|SQM@PM6-ORG",  # no 'driver:' prefix
        "LAMMPS:MD|SQM",  # no '@' in the level
    ],
)
def test_parse_model_chemistry_rejects_malformed(text):
    with pytest.raises(ValueError):
        parse_model_chemistry(text)


# ---------------------------------------------------------------------------
# round trips
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "MOPAC:OPT|SQM@PM6-ORG",
        "LAMMPS:MD|VFF@OPLS-AA",
        "LAMMPS:MD|MOPAC:SQM@PM6-ORG",
        "VASP:OPT|DFT@PBE/PAW@500eV",
        "Psi4:SP|QC@CCSD(T)/cc-pVTZ//Psi4:OPT|DFT@B3LYP/def2-SVP",
    ],
)
def test_round_trip(text):
    """compose(**parse(text)) reproduces the original string."""
    parsed = parse_model_chemistry(text)
    kwargs = {
        "driver": parsed["driver"],
        "task": parsed["task"],
        "owner": parsed["owner"],
        "type": parsed["type"],
        "method": parsed["method"],
        "basis": parsed["basis"],
        "cutoff": parsed["cutoff"],
    }
    if parsed["geometry"] is not None:
        g = parsed["geometry"]
        kwargs["geometry"] = {
            "driver": g["driver"],
            "task": g["task"],
            "owner": g["owner"],
            "type": g["type"],
            "method": g["method"],
            "basis": g["basis"],
            "cutoff": g["cutoff"],
        }
    assert compose_model_chemistry(**kwargs) == text


# ---------------------------------------------------------------------------
# compose -- owner handling and validation
# ---------------------------------------------------------------------------
def test_compose_omits_owner_when_equal_to_driver():
    s = compose_model_chemistry(
        driver="LAMMPS", task="MD", owner="LAMMPS", type="VFF", method="OPLS-AA"
    )
    assert s == "LAMMPS:MD|VFF@OPLS-AA"


def test_compose_writes_owner_under_delegation():
    s = compose_model_chemistry(
        driver="LAMMPS", task="MD", owner="MOPAC", type="SQM", method="PM6-ORG"
    )
    assert s == "LAMMPS:MD|MOPAC:SQM@PM6-ORG"


def test_compose_rejects_cutoff_without_basis():
    with pytest.raises(ValueError):
        compose_model_chemistry(
            driver="VASP", task="OPT", type="DFT", method="PBE", cutoff="500eV"
        )


@pytest.mark.parametrize(
    "text,owner,basis",
    [
        ("ORCA:DFT@PBE0/bse:cc-pVTZ", "ORCA", "bse:cc-pVTZ"),  # owner + bse basis
        ("DFT@PBE0/bse:cc-pVTZ", None, "bse:cc-pVTZ"),  # no owner + bse basis
    ],
)
def test_parse_level_bse_basis(text, owner, basis):
    """A 'bse:NAME' basis prefix is kept on the basis, not read as an owner."""
    parsed = parse_level(text)
    assert parsed["owner"] == owner
    assert parsed["basis"] == basis
    assert parsed["method"] == "PBE0"


def test_compose_bse_basis_round_trip():
    """A 'bse:' basis composes and re-parses (the ':' in the basis is allowed)."""
    s = compose_model_chemistry(
        driver="ORCA", task="SP", type="DFT", method="PBE0", basis="bse:cc-pVTZ"
    )
    assert s == "ORCA:SP|DFT@PBE0/bse:cc-pVTZ"
    assert parse_level("DFT@PBE0/bse:cc-pVTZ")["basis"] == "bse:cc-pVTZ"


def test_compose_rejects_reserved_in_token():
    with pytest.raises(ValueError):
        compose_model_chemistry(
            driver="LAMMPS", task="M|D", type="VFF", method="OPLS-AA"
        )


# ---------------------------------------------------------------------------
# comparability_key -- programs stripped
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, key",
    [
        ("MOPAC:OPT|SQM@PM6-ORG", "OPT|SQM@PM6-ORG"),
        ("LAMMPS:MD|MOPAC:SQM@PM6-ORG", "MD|SQM@PM6-ORG"),
        ("LAMMPS:MD|VFF@OPLS-AA", "MD|VFF@OPLS-AA"),
        ("VASP:OPT|DFT@PBE/PAW@500eV", "OPT|DFT@PBE/PAW@500eV"),
        (
            "Psi4:SP|QC@CCSD(T)/cc-pVTZ//Psi4:OPT|DFT@B3LYP/def2-SVP",
            "SP|QC@CCSD(T)/cc-pVTZ//OPT|DFT@B3LYP/def2-SVP",
        ),
    ],
)
def test_comparability_key(text, key):
    assert comparability_key(parse_model_chemistry(text)) == key


def test_comparability_key_ignores_program_differences():
    """The B3LYP lesson: same task+theory, different codes -> same key."""
    a = comparability_key(parse_model_chemistry("MOPAC:OPT|SQM@PM6-ORG"))
    b = comparability_key(parse_model_chemistry("LAMMPS:OPT|MOPAC:SQM@PM6-ORG"))
    assert a == b == "OPT|SQM@PM6-ORG"
