.. _user-guide:

**********
User Guide
**********

..
    <remove the dots above and this line and unindent the toctree to expose it>
    Contents:

    .. toctree::
       :glob:
       :maxdepth: 2
       :titlesonly:

       *

Settings that depend on each other
==================================

Which settings apply can depend on others. The step's dialogs show only the settings
that apply with the current choices, and the same rules are used when a flowchart is
built or edited without the editor (``seamm-flowchart`` or SEAMM's MCP server): a
setting that would have no effect is refused, with the reason, and a value that
contradicts another is refused too. See "Flowcharts without the editor" in SEAMM's user
guide.

A model chemistry that none of the installed programs offers is refused when the
flowchart is built, not only when it runs. The basis set is a free choice and is not
part of that check.

Machine-learned forcefields
===========================

A machine-learned forcefield, ``xnn:MLFF@<model>``, has two more settings, shown only
for it:

* **Checkpoint**: a checkpoint file or a committee's directory, used instead of the
  model chosen above -- e.g. one trained earlier in the same job. A path, relative to
  the job's directory unless absolute, or a variable such as ``$checkpoint``; it must be
  on the machine where the job runs. The model chosen above then only selects the
  program that runs it, so a new checkpoint or committee, not yet in any model
  directory, can be given with any of that program's models.

  A **committee** is a directory of members ``m0``, ``m1``, ..., each holding a
  ``best.pt``, with at least two members; a ``committee.json`` in it may list the
  members to use, e.g. ``{"members": ["m0", "m1", "m3"]}``. It runs as the
  committee-mean engine of the Active Learning step, which must be installed with
  SEAMM. See `Committees`_ in the xnn step's user guide.

  The program names the model chemistry:

  - a checkpoint with a name of its own is called by its file stem, e.g.
    ``xnn:MLFF@water_mace`` for ``water_mace.pt``;
  - a generic ``best.pt`` or ``last.pt``, as training writes, is called after its
    directory, with the start of a hash of the weights, e.g. ``xnn:MLFF@x013_m1-3f9a2c``;
  - a committee is called by its directory's name or, when that is just
    ``committee``, by its parent's with the start of a hash of its members, e.g.
    ``xnn:MLFF@1-committee-5c20d7``.

  So the name is that of the weights: retraining in the same place gives a new one.
* **Engine options**: options for the model's engine in this run, e.g. ``--eeq-reuse``
  or ``--dispersion "{regime: large}"`` for xnn.

.. _Committees: https://molssi-seamm.github.io/xnn_step/user_guide/index.html#committees

Forcefields
===========

Forcefields are model chemistries too, offered by the Forcefield plug-in: ``FF@oplsaa``
for a classical forcefield and ``ReaxFF@CHO_cho_2008`` for a ReaxFF parameter set. They
have no program, since the step that uses them -- LAMMPS, or Packmol to type the
molecules it packs -- evaluates them itself, so the dialog shows no **Program** for them.
A forcefield from one of your own files (``personal:`` or ``local:``) is sent with a job
submitted to a JobServer.


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
