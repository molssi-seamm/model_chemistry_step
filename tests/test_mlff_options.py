#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A machine-learned forcefield's checkpoint by path and engine options."""

import types

from model_chemistry_step import ModelChemistry, ModelChemistryParameters


def test_the_mlff_options_apply_only_to_an_mlff():
    P = ModelChemistryParameters()
    for key in ("checkpoint", "engine options"):
        assert P.applies(key, {"model_chemistry": "xnn:MLFF@water"})
        assert P.applies(key, {"model_chemistry": "$mc"})
        assert not P.applies(key, {"model_chemistry": "MOPAC:SQM@PM7"})
        assert "MLFF" in P.not_applicable_reason(key, {"model_chemistry": "FF@oplsaa"})


def test_a_checkpoint_is_checked_when_it_runs(monkeypatch):
    """With a checkpoint the model need not be one of those listed."""
    from model_chemistry_step import model_chemistry as mc_module

    monkeypatch.setattr(ModelChemistryParameters, "_available", {(False,): {}})
    P = ModelChemistryParameters()
    values = {"model_chemistry": "xnn:MLFF@epoch_12", "periodic": "no"}
    assert P.problems(values)  # not offered
    values["checkpoint"] = "train/epoch_12.pt"
    assert P.problems(values) == []
    assert mc_module  # imported for the patch target


class _Xnn:
    """The xnn step's side: describes a checkpoint given by path."""

    @classmethod
    def model_chemistry_for_checkpoint(cls, path):
        return {
            "model_chemistry": f"xnn:MLFF@{path.stem}",
            "type": "MLFF",
            "path": str(path),
            "mdi_capable": True,
        }


def test_a_checkpoint_by_path(tmp_path):
    step = ModelChemistry()
    step._id = ("1",)
    step.flowchart = types.SimpleNamespace(
        root_directory=str(tmp_path),
        plugin_manager=types.SimpleNamespace(get=lambda name: _Xnn),
        data_path=None,
    )
    available = {
        "xnn:MLFF@water": {"owner": "xnn", "type": "MLFF", "step": "xnn"},
        "MOPAC:SQM@PM7": {"owner": "MOPAC", "type": "SQM", "step": "MOPAC"},
    }
    mc = step._from_checkpoint("xnn:MLFF@water", "train/epoch_12.pt", available)
    assert mc["level"] == "xnn:MLFF@epoch_12" and mc["step"] == "xnn"
    assert mc["options"]["path"] == str(tmp_path / "train" / "epoch_12.pt")
    mc = step._from_checkpoint("MLFF@x", "/abs/best.pt", available)
    assert mc["options"]["path"] == "/abs/best.pt"
