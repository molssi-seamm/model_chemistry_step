# -*- coding: utf-8 -*-

"""Metadata for the Model Chemistry step.

The Model Chemistry step does not run a calculation. It lets the user select a
model chemistry and stores it as the workspace variable ``_model_chemistry`` for
downstream steps (e.g. LAMMPS) to consume. It therefore produces no
computational properties of its own, so ``metadata`` is an empty dictionary.

The available model chemistries are *discovered* at runtime from the installed
program plug-ins -- each program step (e.g. ``mopac_step``) exposes a
``get_model_chemistry_options()`` classmethod -- so they are not declared here.
"""

metadata = {}
