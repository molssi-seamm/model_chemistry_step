#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for model_chemistry.resolve_level: dereferencing a $variable/
=expression embedded in one component of a level-spec string at run time.
"""

import pytest

from model_chemistry_step.model_chemistry import resolve_level, _dereference


def test_dereference_passes_plain_text_through():
    assert _dereference("DFT", {}) == "DFT"


def test_dereference_passes_none_through():
    assert _dereference(None, {}) is None


def test_dereference_evaluates_dollar_variable():
    assert _dereference("$functional", {"functional": "PBE0"}) == "PBE0"


def test_dereference_evaluates_equals_expression():
    context = {"base": "B3LYP"}
    assert _dereference("=base", context) == "B3LYP"


def test_dereference_double_equals_is_not_an_expression():
    assert _dereference("==", {}) == "=="


def test_resolve_level_unchanged_when_nothing_is_an_expression():
    level = "Psi4:DFT@B3LYP/def2-SVP"
    assert resolve_level(level, {}) == level


def test_resolve_level_unchanged_for_an_unparseable_string():
    # No '@' -- not a valid level spec; left alone rather than raising.
    assert resolve_level("garbage-no-delimiters", {}) == "garbage-no-delimiters"


def test_resolve_level_substitutes_method():
    level = "Psi4:DFT@$functional/def2-SVP"
    context = {"functional": "PBE0"}
    assert resolve_level(level, context) == "Psi4:DFT@PBE0/def2-SVP"


def test_resolve_level_substitutes_type():
    level = "Psi4:$level_type@B3LYP/def2-SVP"
    context = {"level_type": "DFT"}
    assert resolve_level(level, context) == "Psi4:DFT@B3LYP/def2-SVP"


def test_resolve_level_substitutes_basis():
    level = "Psi4:DFT@B3LYP/$basis_name"
    context = {"basis_name": "cc-pVTZ"}
    assert resolve_level(level, context) == "Psi4:DFT@B3LYP/cc-pVTZ"


def test_resolve_level_substitutes_owner():
    level = "$program:DFT@B3LYP/def2-SVP"
    context = {"program": "ORCA"}
    assert resolve_level(level, context) == "ORCA:DFT@B3LYP/def2-SVP"


def test_resolve_level_substitutes_multiple_components_at_once():
    level = "DFT@$functional/$basis_name"
    context = {"functional": "PBE0", "basis_name": "def2-TZVP"}
    assert resolve_level(level, context) == "DFT@PBE0/def2-TZVP"


def test_resolve_level_no_basis_stays_absent_after_substitution():
    level = "SQM@$functional"
    context = {"functional": "PM6-ORG"}
    assert resolve_level(level, context) == "SQM@PM6-ORG"


def test_resolve_level_preserves_bse_prefix_on_a_literal_basis():
    level = "DFT@$functional/bse:cc-pVQZ"
    context = {"functional": "B3LYP"}
    assert resolve_level(level, context) == "DFT@B3LYP/bse:cc-pVQZ"


def test_resolve_level_raises_if_substituted_value_has_reserved_character():
    # A variable resolving to something containing '/' would break the
    # grammar downstream -- fail loudly and clearly, not silently.
    level = "DFT@$functional/def2-SVP"
    context = {"functional": "bad/method"}
    with pytest.raises(ValueError):
        resolve_level(level, context)


def test_resolve_level_expression_evaluation_error_propagates():
    level = "DFT@$undefined_variable/def2-SVP"
    with pytest.raises(NameError):
        resolve_level(level, {})
