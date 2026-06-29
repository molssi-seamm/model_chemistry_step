=======
History
=======

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
