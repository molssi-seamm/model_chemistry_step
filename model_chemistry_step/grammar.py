# -*- coding: utf-8 -*-

"""The model-chemistry grammar for SEAMM.

A *model chemistry* names **what was done** (the task), **at what level of
theory** (the potential energy surface), and **by which code(s)** (provenance),
in one parseable string::

    [driver:]task | [owner:]type@method[/basis[@cutoff]]   [ // <unit> ]

* ``driver``  -- the code performing the task (always present).
* ``task``    -- SP | OPT | MD | FREQ | ... (explicit and required).
* ``owner``   -- the code evaluating the PES, written **only** when it differs
  from the driver (i.e. under MDI delegation).
* ``type@method[/basis[@cutoff]]`` -- the level of theory ("level spec").
* ``//``      -- optionally joins an energy unit to the geometry unit it was
  evaluated at (the Pople convention); lowest precedence.

Examples::

    MOPAC:OPT|SQM@PM6-ORG               driver=owner=MOPAC, task=OPT
    LAMMPS:MD|VFF@OPLS-AA               LAMMPS evaluates OPLS-AA itself
    LAMMPS:MD|MOPAC:SQM@PM6-ORG         LAMMPS drives, MOPAC owns the PES (MDI)
    VASP:OPT|DFT@PBE/PAW@500eV          basis PAW, cutoff 500eV
    Psi4:SP|QC@CCSD(T)/cc-pVTZ//Psi4:OPT|DFT@B3LYP/def2-SVP   compound

Stripping ``driver:`` and ``owner:`` yields the program-free **comparability
key** ``task|theory`` -- two results with the same key are comparable
regardless of which code produced them.

The reserved characters ``:`` ``@`` ``/`` ``|`` must not appear inside any
token. A ``cutoff`` requires a ``basis``. See
``molssi-seamm.github.io`` :: ``background/model_chemistry_naming.rst`` for the
full standard.
"""

__all__ = [
    "parse_level",
    "parse_model_chemistry",
    "compose_model_chemistry",
    "comparability_key",
]

# Characters reserved as grammar delimiters; no token may contain them.
RESERVED = ":@/|"


def _check_token(token, what):
    """Raise ValueError if `token` is empty or contains a reserved character."""
    if token == "":
        raise ValueError(f"The {what} is empty.")
    bad = [c for c in RESERVED if c in token]
    if bad:
        raise ValueError(
            f"The {what} '{token}' contains reserved character(s) {bad}; "
            f"the reserved characters are {list(RESERVED)}."
        )


def _compose_theory(type_, method, basis=None, cutoff=None):
    """Build ``type@method[/basis[@cutoff]]`` from its parts (with validation)."""
    _check_token(type_, "type")
    _check_token(method, "method")
    if cutoff is not None and basis is None:
        raise ValueError(
            "A cutoff was given without a basis; the grammar requires "
            "'basis' before '@cutoff'."
        )
    text = f"{type_}@{method}"
    if basis is not None:
        _check_token(basis, "basis")
        text += f"/{basis}"
        if cutoff is not None:
            _check_token(cutoff, "cutoff")
            text += f"@{cutoff}"
    return text


def parse_level(text):
    """Parse a bare level spec ``[owner:]type@method[/basis[@cutoff]]``.

    This is what a program step advertises (via
    ``get_model_chemistry_options``) and what the Model Chemistry step selects;
    it carries no ``driver`` or ``task``.

    Parameters
    ----------
    text : str
        A level spec, e.g. ``"SQM@PM6-ORG"`` or ``"MOPAC:SQM@PM6-ORG"``.

    Returns
    -------
    dict
        Keys ``owner`` (``None`` when absent), ``type``, ``method``, ``basis``,
        ``cutoff`` (the last two may be ``None``), and ``level`` echoing the
        input.

    Raises
    ------
    ValueError
        If the ``@`` separating type from method is missing.
    """
    # An owner is the only place a ':' can legally appear in a level spec
    # (type/method/basis/cutoff are tokens), so a ':' splits owner from theory.
    if ":" in text:
        owner, theory = text.split(":", 1)
        _check_token(owner, "owner")
    else:
        owner, theory = None, text

    if "@" not in theory:
        raise ValueError(
            f"'{text}' is not a valid level spec: missing the '@method' part "
            "(no '@' after the type)."
        )
    type_, method_cluster = theory.split("@", 1)

    if "/" in method_cluster:
        method, basis_cluster = method_cluster.split("/", 1)
        if "@" in basis_cluster:
            basis, cutoff = basis_cluster.split("@", 1)
        else:
            basis, cutoff = basis_cluster, None
    else:
        method, basis, cutoff = method_cluster, None, None

    return {
        "owner": owner,
        "type": type_,
        "method": method,
        "basis": basis,
        "cutoff": cutoff,
        "level": text,
    }


def parse_model_chemistry(text):
    """Parse a full model-chemistry string into its components.

    Parameters
    ----------
    text : str
        A full string ``[driver:]task | [owner:]theory [ // <unit> ]``.

    Returns
    -------
    dict
        Keys ``driver``, ``task``, ``owner``, ``type``, ``method``, ``basis``,
        ``cutoff``, ``level`` (the bare level spec), ``geometry`` (a nested
        parse of the ``//`` unit, or ``None``), and ``comparability_key``.

    Raises
    ------
    ValueError
        If the ``|`` (driver:task vs. level) or ``driver:`` / ``@`` delimiters
        are missing.
    """
    # '//' has the lowest precedence: split the energy unit from the geometry.
    if "//" in text:
        energy_text, geom_text = text.split("//", 1)
        geometry = parse_model_chemistry(geom_text)
    else:
        energy_text, geometry = text, None

    if "|" not in energy_text:
        raise ValueError(
            f"'{text}' is not a valid model chemistry: missing the '|' that "
            "separates 'driver:task' from the level of theory."
        )
    task_part, level_part = energy_text.split("|", 1)

    if ":" not in task_part:
        raise ValueError(
            f"'{text}' is not a valid model chemistry: missing the 'driver:' "
            "prefix before the task."
        )
    driver, task = task_part.split(":", 1)
    _check_token(driver, "driver")
    _check_token(task, "task")

    level = parse_level(level_part)

    parsed = {
        "driver": driver,
        "task": task,
        "owner": level["owner"],
        "type": level["type"],
        "method": level["method"],
        "basis": level["basis"],
        "cutoff": level["cutoff"],
        "level": level["level"],
        "geometry": geometry,
    }
    parsed["comparability_key"] = comparability_key(parsed)
    return parsed


def compose_model_chemistry(
    driver,
    task,
    *,
    owner=None,
    type,  # noqa: A002  (kwarg name is part of the public grammar API)
    method,
    basis=None,
    cutoff=None,
    geometry=None,
):
    """Build the canonical model-chemistry string. Inverse of the parser.

    Parameters
    ----------
    driver : str
        The code performing the task.
    task : str
        SP | OPT | MD | FREQ | ...
    owner : str, optional
        The PES-owning code. Omitted from the output when ``None`` or equal to
        ``driver`` (driver == owner needs no explicit owner).
    type, method : str
        The level-of-theory family and specific method.
    basis, cutoff : str, optional
        ``cutoff`` requires ``basis``.
    geometry : dict, optional
        A dict of the same keyword arguments; appended as ``//<unit>`` (the
        geometry the energy was evaluated at).

    Returns
    -------
    str
        The canonical ``driver:task|[owner:]theory[//<unit>]`` string.
    """
    _check_token(driver, "driver")
    _check_token(task, "task")

    theory = _compose_theory(type, method, basis, cutoff)
    if owner is None or owner == driver:
        level = theory
    else:
        _check_token(owner, "owner")
        level = f"{owner}:{theory}"

    text = f"{driver}:{task}|{level}"

    if geometry is not None:
        text += "//" + compose_model_chemistry(**geometry)
    return text


def comparability_key(parsed):
    """Return the program-free comparability key ``task|theory``.

    Drops ``driver`` and ``owner`` from each unit, so results from different
    codes at the same task and level of theory share a key.

    Parameters
    ----------
    parsed : dict
        The dict returned by :func:`parse_model_chemistry` (needs ``task``,
        ``type``, ``method``, ``basis``, ``cutoff`` and optionally
        ``geometry``).

    Returns
    -------
    str
        ``task|theory`` (or ``task|theory//task|theory`` for a compound).
    """
    theory = _compose_theory(
        parsed["type"], parsed["method"], parsed.get("basis"), parsed.get("cutoff")
    )
    key = f"{parsed['task']}|{theory}"
    geometry = parsed.get("geometry")
    if geometry is not None:
        key += "//" + comparability_key(geometry)
    return key
