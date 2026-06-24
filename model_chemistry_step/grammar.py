# -*- coding: utf-8 -*-

"""The model-chemistry grammar for SEAMM.

A *model chemistry* is named with a compact, code-agnostic string::

    Program:Type@Method[/Basis[@Cutoff]]

Examples
--------
========================  =======  ====  =======   ========  ======
string                    Program  Type  Method    Basis     Cutoff
========================  =======  ====  =======   ========  ======
MOPAC:SQM@PM6-ORG         MOPAC    SQM   PM6-ORG   None      None
Psi4:DFT@B3LYP/def2-SVP   Psi4     DFT   B3LYP     def2-SVP  None
VASP:DFT@PBE/PAW@500eV    VASP     DFT   PBE       PAW       500eV
========================  =======  ====  =======   ========  ======

The delimiters ``:``, ``@`` and ``/`` are reserved and must not appear inside
the Program, Type, Method, Basis, or Cutoff tokens. A ``Basis`` is required if
a ``Cutoff`` is given.
"""

__all__ = ["parse_model_chemistry", "compose_model_chemistry"]


def parse_model_chemistry(text):
    """Parse a model-chemistry string into its components.

    Parameters
    ----------
    text : str
        A string of the form ``Program:Type@Method[/Basis[@Cutoff]]``.

    Returns
    -------
    dict
        Keys ``program``, ``type``, ``method``, ``basis`` and ``cutoff`` (the
        last two may be ``None``), plus ``model_chemistry`` echoing the input.

    Raises
    ------
    ValueError
        If `text` lacks the required ``:`` or ``@`` delimiters.
    """
    if ":" not in text:
        raise ValueError(
            f"'{text}' is not a valid model chemistry: missing the "
            "'Program:' prefix (no ':')."
        )
    program, rest = text.split(":", 1)

    if "@" not in rest:
        raise ValueError(
            f"'{text}' is not a valid model chemistry: missing the "
            "'@Method' part (no '@' after the type)."
        )
    type_, method_cluster = rest.split("@", 1)

    if "/" in method_cluster:
        method, basis_cluster = method_cluster.split("/", 1)
        if "@" in basis_cluster:
            basis, cutoff = basis_cluster.split("@", 1)
        else:
            basis, cutoff = basis_cluster, None
    else:
        method, basis, cutoff = method_cluster, None, None

    return {
        "program": program,
        "type": type_,
        "method": method,
        "basis": basis,
        "cutoff": cutoff,
        "model_chemistry": text,
    }


def compose_model_chemistry(components):
    """Build the canonical model-chemistry string from its components.

    The inverse of :func:`parse_model_chemistry`.

    Parameters
    ----------
    components : dict
        A dict with keys ``program``, ``type`` and ``method``, and optionally
        ``basis`` and ``cutoff`` (as returned by ``parse_model_chemistry``).

    Returns
    -------
    str
        The canonical ``Program:Type@Method[/Basis[@Cutoff]]`` string.

    Raises
    ------
    ValueError
        If a required component is missing, or a cutoff is given without a
        basis (the grammar requires a basis before a cutoff).
    """
    try:
        program = components["program"]
        type_ = components["type"]
        method = components["method"]
    except KeyError as e:
        raise ValueError(f"Missing required model-chemistry component: {e}")

    basis = components.get("basis")
    cutoff = components.get("cutoff")

    if cutoff is not None and basis is None:
        raise ValueError(
            "A cutoff was given without a basis; the grammar requires "
            "'Basis' before '@Cutoff'."
        )

    text = f"{program}:{type_}@{method}"
    if basis is not None:
        text += f"/{basis}"
        if cutoff is not None:
            text += f"@{cutoff}"
    return text
