#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Headless tests for the cascading-selector logic in ``TkModelChemistry``.

The dialog itself needs a display, but the discovery/cascade logic is pure: it
only touches ``self._model_chemistries``, the combobox widgets, and the node's
parameters. So we drive the methods unbound against a lightweight fake ``self``,
with no Tk root.
"""

import seamm

from model_chemistry_step.tk_model_chemistry import TkModelChemistry
from model_chemistry_step.grammar import parse_model_chemistry

# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class _Combo:
    """Stand-in for a LabeledCombobox: set/get plus a .combobox.configure."""

    def __init__(self, value=""):
        self._value = value
        self.values = None

    def set(self, value):
        self._value = value

    def get(self):
        return self._value

    @property
    def combobox(self):
        return self

    def configure(self, values=None, **kwargs):
        if values is not None:
            self.values = list(values)


class _Param:
    def __init__(self, value=None):
        self.value = value


class _Node:
    def __init__(self, model_chemistry=None):
        self.parameters = {"model_chemistry": _Param(model_chemistry)}


class _FakeTk(TkModelChemistry):
    """A TkModelChemistry whose Tk wiring is replaced by fakes.

    Subclassing (rather than duck-typing) lets the real methods dispatch
    through ``self`` -- ``_cascade`` calling ``self._types()``, and
    ``handle_dialog`` calling ``super()`` -- without a display. The
    display-requiring base ``__init__`` is deliberately skipped.
    """

    def __init__(self, model_chemistries, periodic="no", model_chemistry=None):
        self._model_chemistries = model_chemistries
        self._widgets = {
            "periodic": _Combo(periodic),
            "type": _Combo(),
            "method": _Combo(),
            "program": _Combo(),
        }
        self.node = _Node(model_chemistry)

    def __getitem__(self, key):
        return self._widgets[key]

    def is_expr(self, value):
        return isinstance(value, str) and value.startswith("$")


def _wrap(key, step):
    return {
        **parse_model_chemistry(key),
        "step": step,
        "options": {"model_chemistry": key},
    }


# SQM has two methods from one program; DFT@B3LYP is offered by two programs
# with different bases -- exercises Program disambiguation and basis retention.
SAMPLE = {
    "MOPAC:SQM@PM6-ORG": _wrap("MOPAC:SQM@PM6-ORG", "MOPAC"),
    "MOPAC:SQM@AM1": _wrap("MOPAC:SQM@AM1", "MOPAC"),
    "Psi4:DFT@B3LYP/def2-SVP": _wrap("Psi4:DFT@B3LYP/def2-SVP", "Psi4"),
    "Gaussian:DFT@B3LYP/6-31G*": _wrap("Gaussian:DFT@B3LYP/6-31G*", "Gaussian"),
}


# --------------------------------------------------------------------------- #
# _types / _methods / _programs
# --------------------------------------------------------------------------- #


def test_levels_are_derived_and_sorted():
    fs = _FakeTk(SAMPLE)
    assert TkModelChemistry._types(fs) == ["DFT", "SQM"]
    assert TkModelChemistry._methods(fs, "SQM") == ["AM1", "PM6-ORG"]
    assert TkModelChemistry._methods(fs, "DFT") == ["B3LYP"]
    assert TkModelChemistry._programs(fs, "DFT", "B3LYP") == ["Gaussian", "Psi4"]
    assert TkModelChemistry._programs(fs, "SQM", "PM6-ORG") == ["MOPAC"]


# --------------------------------------------------------------------------- #
# _cascade
# --------------------------------------------------------------------------- #


def test_cascade_keeps_a_fully_valid_selection_and_sets_choices():
    fs = _FakeTk(SAMPLE)
    TkModelChemistry._cascade(fs, "SQM", "PM6-ORG", "MOPAC")
    assert (fs["type"].get(), fs["method"].get(), fs["program"].get()) == (
        "SQM",
        "PM6-ORG",
        "MOPAC",
    )
    assert fs["type"].values == ["DFT", "SQM"]
    assert fs["method"].values == ["AM1", "PM6-ORG"]
    assert fs["program"].values == ["MOPAC"]


def test_cascade_falls_back_when_a_level_is_invalid():
    fs = _FakeTk(SAMPLE)
    # Bad method -> falls back to the first available method (and its program).
    TkModelChemistry._cascade(fs, "SQM", "does-not-exist", None)
    assert fs["method"].get() == "AM1"
    assert fs["program"].get() == "MOPAC"


def test_cascade_program_autoselects_when_unique():
    fs = _FakeTk(SAMPLE)
    TkModelChemistry._cascade(fs, "SQM", "PM6-ORG", None)
    assert fs["program"].get() == "MOPAC"


def test_cascade_picks_first_program_but_keeps_a_valid_one():
    fs = _FakeTk(SAMPLE)
    TkModelChemistry._cascade(fs, "DFT", "B3LYP", None)
    assert fs["program"].get() == "Gaussian"  # first sorted of two
    TkModelChemistry._cascade(fs, "DFT", "B3LYP", "Psi4")
    assert fs["program"].get() == "Psi4"  # valid current kept


def test_cascade_handles_empty_discovery():
    fs = _FakeTk({})
    TkModelChemistry._cascade(fs, "SQM", "PM6-ORG", "MOPAC")
    assert fs["type"].get() == ""
    assert fs["method"].get() == ""
    assert fs["program"].get() == ""


# --------------------------------------------------------------------------- #
# _load_from_parameter -- decompose the stored string onto the selectors
# --------------------------------------------------------------------------- #


def _record_cascade(fs):
    calls = []
    fs._discover = lambda: None
    fs._cascade = lambda t, m, p: calls.append((t, m, p))
    return calls


def test_load_decomposes_a_canonical_string():
    fs = _FakeTk(SAMPLE, model_chemistry="Psi4:DFT@B3LYP/def2-SVP")
    calls = _record_cascade(fs)
    TkModelChemistry._load_from_parameter(fs)
    assert calls == [("DFT", "B3LYP", "Psi4")]


def test_load_leaves_selectors_unset_for_an_expression():
    fs = _FakeTk(SAMPLE, model_chemistry="$MODEL_CHEMISTRY")
    calls = _record_cascade(fs)
    TkModelChemistry._load_from_parameter(fs)
    assert calls == [(None, None, None)]


def test_load_leaves_selectors_unset_for_an_unparseable_string():
    fs = _FakeTk(SAMPLE, model_chemistry="garbage-no-delimiters")
    calls = _record_cascade(fs)
    TkModelChemistry._load_from_parameter(fs)
    assert calls == [(None, None, None)]


# --------------------------------------------------------------------------- #
# handle_dialog -- compose the selection back into the parameter on OK
# --------------------------------------------------------------------------- #


def test_ok_stores_the_discovered_canonical_string(monkeypatch):
    monkeypatch.setattr(seamm.TkNode, "handle_dialog", lambda self, result: None)
    fs = _FakeTk(SAMPLE)
    fs["type"].set("SQM")
    fs["method"].set("PM6-ORG")
    fs["program"].set("MOPAC")

    TkModelChemistry.handle_dialog(fs, "OK")

    assert fs.node.parameters["model_chemistry"].value == "MOPAC:SQM@PM6-ORG"


def test_ok_keeps_basis_and_cutoff_via_the_discovered_key(monkeypatch):
    """Choosing Psi4 DFT B3LYP must store the full key with its basis, not a
    recomposed Program:Type@Method that drops it."""
    monkeypatch.setattr(seamm.TkNode, "handle_dialog", lambda self, result: None)
    fs = _FakeTk(SAMPLE)
    fs["type"].set("DFT")
    fs["method"].set("B3LYP")
    fs["program"].set("Psi4")

    TkModelChemistry.handle_dialog(fs, "OK")

    assert fs.node.parameters["model_chemistry"].value == "Psi4:DFT@B3LYP/def2-SVP"


def test_cancel_does_not_change_the_parameter(monkeypatch):
    monkeypatch.setattr(seamm.TkNode, "handle_dialog", lambda self, result: None)
    fs = _FakeTk(SAMPLE, model_chemistry="MOPAC:SQM@PM6-ORG")
    fs["type"].set("SQM")
    fs["method"].set("AM1")
    fs["program"].set("MOPAC")

    TkModelChemistry.handle_dialog(fs, "Cancel")

    assert fs.node.parameters["model_chemistry"].value == "MOPAC:SQM@PM6-ORG"
