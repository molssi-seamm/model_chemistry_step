#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `model_chemistry_step` package."""

import pytest  # noqa: F401
import model_chemistry_step  # noqa: F401


def test_construction():
    """Just create an object and test its type."""
    result = model_chemistry_step.ModelChemistry()
    assert (
        str(type(result))
        == "<class 'model_chemistry_step.model_chemistry.ModelChemistry'>"
    )
