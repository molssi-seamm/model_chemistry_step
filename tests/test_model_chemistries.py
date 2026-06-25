#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for discovery and storage in the Model Chemistry step.

Two layers are exercised:

* The discovery *logic* of ``ModelChemistry.model_chemistries()`` -- iterating
  the ``org.molssi.seamm`` Stevedore namespace and calling
  ``get_model_chemistry_options()`` on every helper that defines it -- is tested
  against fake provider classes injected in place of the real ExtensionManager,
  so these tests run anywhere and pin the contract independently of what happens
  to be installed.

* The end-to-end behaviour (real discovery + ``run()`` storing the
  ``_model_chemistry`` workspace variable) is tested against the real
  ``mopac_step`` provider, and skipped if it is not installed.
"""

import tempfile

import pytest

import seamm
import model_chemistry_step
from model_chemistry_step import ModelChemistry
from model_chemistry_step import model_chemistry as mc_module

# --------------------------------------------------------------------------- #
# Fakes for testing the discovery logic without a real environment
# --------------------------------------------------------------------------- #


class _Ext:
    """Stand-in for a stevedore Extension: just a name and a plugin object."""

    def __init__(self, name, plugin):
        self.name = name
        self.plugin = plugin


class _NoMethod:
    """A helper class that does NOT expose get_model_chemistry_options."""


def _provider(options, *, record=None, raises=False):
    """Build a fake program-step helper class exposing the discovery method.

    ``options`` is what the classmethod returns; ``record`` (if given) collects
    the ``(periodic_only, mdi_only)`` it was called with; ``raises`` makes it
    blow up, to test that discovery survives a misbehaving provider.
    """

    class _Provider:
        @classmethod
        def get_model_chemistry_options(cls, periodic_only=False, mdi_only=False):
            if record is not None:
                record.append((periodic_only, mdi_only))
            if raises:
                raise RuntimeError("provider blew up")
            return options

    return _Provider


def _patch_namespace(monkeypatch, exts):
    """Replace stevedore.ExtensionManager so iterating it yields ``exts``."""

    def factory(*args, **kwargs):
        assert kwargs["namespace"] == "org.molssi.seamm"
        return list(exts)

    monkeypatch.setattr(mc_module.stevedore, "ExtensionManager", factory)


# An option entry as a program step would return it (extra keys must be carried
# through verbatim in the wrapper's "options").
def _option(model_chemistry, **extra):
    return {"model_chemistry": model_chemistry, **extra}


# --------------------------------------------------------------------------- #
# Discovery logic (fake providers)
# --------------------------------------------------------------------------- #


def test_collects_only_helpers_that_expose_the_method(monkeypatch):
    """A plug-in without get_model_chemistry_options is silently ignored;
    one that has it contributes its options."""
    provider = _provider({"PM6-ORG": _option("FOO:SQM@PM6-ORG")})
    _patch_namespace(
        monkeypatch,
        [_Ext("foo", provider), _Ext("plain", _NoMethod)],
    )

    result = ModelChemistry().model_chemistries()

    assert set(result) == {"FOO:SQM@PM6-ORG"}


def test_a_provider_that_raises_is_skipped_not_fatal(monkeypatch):
    """One provider raising must not lose the others -- discovery logs and
    moves on."""
    good = _provider({"PM6": _option("FOO:SQM@PM6")})
    bad = _provider({}, raises=True)
    _patch_namespace(
        monkeypatch,
        [_Ext("bad", bad), _Ext("foo", good)],
    )

    result = ModelChemistry().model_chemistries()

    assert set(result) == {"FOO:SQM@PM6"}


def test_duplicate_key_keeps_the_first_provider(monkeypatch):
    """If two steps offer the same canonical string, the first one wins and
    its step name is recorded."""
    first = _provider({"x": _option("FOO:SQM@PM6", tag="first")})
    second = _provider({"x": _option("FOO:SQM@PM6", tag="second")})
    _patch_namespace(
        monkeypatch,
        [_Ext("first_step", first), _Ext("second_step", second)],
    )

    result = ModelChemistry().model_chemistries()

    assert set(result) == {"FOO:SQM@PM6"}
    assert result["FOO:SQM@PM6"]["step"] == "first_step"
    assert result["FOO:SQM@PM6"]["options"]["tag"] == "first"


def test_wrapper_has_the_full_model_chemistry_contract(monkeypatch):
    """Each wrapper carries the parsed components, the owning step name, and
    the verbatim options block -- exactly the _model_chemistry schema."""
    opts = _option("VASP:DFT@PBE/PAW@500eV", mdi_capable=False, note="hi")
    _patch_namespace(monkeypatch, [_Ext("vasp", _provider({"PBE": opts}))])

    w = ModelChemistry().model_chemistries()["VASP:DFT@PBE/PAW@500eV"]

    assert set(w) == {
        "owner",
        "type",
        "method",
        "basis",
        "cutoff",
        "level",
        "step",
        "options",
    }
    assert (w["owner"], w["type"], w["method"]) == ("VASP", "DFT", "PBE")
    assert (w["basis"], w["cutoff"]) == ("PAW", "500eV")
    assert w["step"] == "vasp"
    assert w["options"] is opts  # carried through unchanged


def test_filter_flags_are_forwarded_to_providers(monkeypatch):
    """periodic_only / mdi_only are passed straight through to each provider's
    get_model_chemistry_options()."""
    calls = []
    _patch_namespace(
        monkeypatch,
        [_Ext("foo", _provider({}, record=calls))],
    )

    ModelChemistry().model_chemistries(periodic_only=True, mdi_only=True)

    assert calls == [(True, True)]


# --------------------------------------------------------------------------- #
# End-to-end against the real mopac_step provider
# --------------------------------------------------------------------------- #

mopac_step = pytest.importorskip(
    "mopac_step", reason="real-discovery tests need mopac_step installed"
)


@pytest.fixture
def make_node():
    """Build a ModelChemistry node wired into a minimal runnable flowchart.

    Also binds a fresh workspace-variable store, the way a running flowchart
    does, so set_variable/get_variable work.
    """

    def _make(model_chemistry, periodic="no"):
        flowchart = seamm.Flowchart()
        flowchart.root_directory = tempfile.mkdtemp()
        node = ModelChemistry(flowchart=flowchart)
        flowchart.add_node(node)
        node._id = ("1",)
        node.parameters["model_chemistry"].value = model_chemistry
        node.parameters["periodic"].value = periodic
        return node

    seamm.flowchart_variables = seamm.Variables()
    return _make


def test_real_discovery_finds_mopac():
    """Against the installed mopac_step, the canonical thin-line target is
    discovered and resolves back to the MOPAC step."""
    result = ModelChemistry().model_chemistries()

    assert "MOPAC:SQM@PM6-ORG" in result
    w = result["MOPAC:SQM@PM6-ORG"]
    assert w["step"] == "MOPAC"
    assert (w["owner"], w["type"], w["method"]) == ("MOPAC", "SQM", "PM6-ORG")


def test_real_discovery_matches_mopac_options_directly():
    """The MOPAC entries that discovery surfaces are exactly the canonical
    strings MOPACStep.get_model_chemistry_options() reports, for every filter
    combination -- cross-checked against the source of truth rather than a
    hard-coded list."""
    node = ModelChemistry()
    for periodic_only in (False, True):
        for mdi_only in (False, True):
            discovered = {
                key
                for key, w in node.model_chemistries(
                    periodic_only=periodic_only, mdi_only=mdi_only
                ).items()
                if w["step"] == "MOPAC"
            }
            expected = {
                opt["model_chemistry"]
                for opt in mopac_step.MOPACStep.get_model_chemistry_options(
                    periodic_only=periodic_only, mdi_only=mdi_only
                ).values()
            }
            assert discovered == expected
            assert len(expected) > 0  # not two empty sets agreeing


def test_run_stores_the_selected_model_chemistry(make_node):
    """run() publishes the chosen model chemistry as _model_chemistry for
    downstream steps."""
    node = make_node("MOPAC:SQM@PM6-ORG")
    node.run()

    stored = node.get_variable("_model_chemistry")
    assert stored["level"] == "MOPAC:SQM@PM6-ORG"
    assert stored["owner"] == "MOPAC"
    assert stored["step"] == "MOPAC"
    assert stored["method"] == "PM6-ORG"
    assert stored["options"]["mdi_capable"] is True


def test_run_periodic_filter_allows_a_validated_method(make_node):
    """PM6-ORG is periodic-validated, so it is accepted under periodic=yes."""
    node = make_node("MOPAC:SQM@PM6-ORG", periodic="yes")
    node.run()
    assert node.get_variable("_model_chemistry")["level"] == "MOPAC:SQM@PM6-ORG"


def test_run_periodic_filter_rejects_a_non_validated_method(make_node):
    """AM1 is MDI-capable but not periodic-validated, so periodic=yes must
    reject it with a helpful error."""
    node = make_node("MOPAC:SQM@AM1", periodic="yes")
    with pytest.raises(ValueError, match="not available for periodic systems"):
        node.run()


def test_run_rejects_an_unknown_model_chemistry(make_node):
    """A string no installed step offers is rejected."""
    node = make_node("NOPE:XX@bogus")
    with pytest.raises(ValueError, match="is not available"):
        node.run()


def test_grammar_is_reexported_from_the_package():
    """The grammar helpers are available at the package top level for
    consumers (LAMMPS, program steps)."""
    assert hasattr(model_chemistry_step, "parse_level")
    assert hasattr(model_chemistry_step, "parse_model_chemistry")
    assert hasattr(model_chemistry_step, "compose_model_chemistry")
    assert hasattr(model_chemistry_step, "comparability_key")
