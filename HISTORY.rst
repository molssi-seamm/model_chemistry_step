=======
History
=======

2026.7.31 -- Bugfix: crash and stale picker on Type change / direct-entry edits
    * Fixed a crash ("TypeError: object of type 'NoneType' has no len()") when
      changing the Type selector (e.g. to DFT) in the Model Chemistry dialog.
    * Editing the model-chemistry string in direct-entry mode and then
      switching back to the guided picker now correctly reflects the edit. A
      component that isn't a currently offered choice (e.g. a method not
      advertised by any installed program) is now shown blank, instead of the
      picker silently substituting some other, unrelated valid choice -- which
      made an edit look like it had been ignored.

2026.7.30 -- $variables in the Type/Method/Basis selectors
    * The Type and Method (e.g. DFT functional) selectors now accept typed text,
      including a '$variable' or '=expression', so a preceding Loop step can vary
      the model chemistry from one iteration to the next.
    * A '$variable' typed into any of Type, Method, Program, or Basis is now
      actually evaluated at run time. Previously only a variable that was the
      *entire* model-chemistry value was dereferenced; one embedded in a composed
      string (e.g. the Basis field alone) was passed through to downstream steps
      as the literal, unresolved text.
    * Added a checkbox to enter the whole model-chemistry string directly as
      text, instead of using the Type/Method/Program/Basis picker -- by far the
      simplest way to use a '$variable', since it sidesteps the picker's
      discovery/validation entirely. The dialog switches to this mode
      automatically when the stored value can't be decomposed by the picker
      (e.g. it is itself a '$variable').

2026.6.28 -- Basis-set selection
    * Added a basis-set field to the dialog for levels of theory that use a basis
      (HF, DFT, MP2, coupled cluster), using the shared Basis Set Exchange picker
      (choose elements on a periodic table, then a covering basis). It is hidden
      for methods that use no basis (semiempirical, forcefield, MLFF).
    * The basis is the user's free choice -- any Basis Set Exchange basis (stored
      as 'bse:NAME'), not just the few a program advertises. A level of theory is
      accepted as long as a program offers its type and method.
    * The model-chemistry grammar accepts a 'bse:' prefix on the basis.

2026.6.22 (2026-06-22)
----------------------

* Plug-in created using the SEAMM plug-in cookiecutter.
