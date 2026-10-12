# -*- coding: utf-8 -*-

"""Non-graphical part of the Model Chemistry step in a SEAMM flowchart"""

import inspect
import logging
from pathlib import Path
import shlex
import importlib.resources
import pprint

import model_chemistry_step
import molsystem
import seamm
from seamm_util import ureg, Q_  # noqa: F401
import seamm_util.printing as printing
from seamm_util.printing import FormattedText as __
import stevedore

from .grammar import parse_level, _compose_theory

# In addition to the normal logger, two logger-like printing facilities are
# defined: "job" and "printer". "job" send output to the main job.out file for
# the job, and should be used very sparingly, typically to echo what this step
# will do in the initial summary of the job.
#
# "printer" sends output to the file "step.out" in this steps working
# directory, and is used for all normal output from this step.

logger = logging.getLogger(__name__)
job = printing.getPrinter()
printer = printing.getPrinter("Model Chemistry")

# Add this module's properties to the standard properties
path = importlib.resources.files("model_chemistry_step") / "data"
csv_file = path / "properties.csv"
if path.exists():
    molsystem.add_properties_from_file(csv_file)


def _dereference(token, context):
    """Evaluate `token` if it is a ``$variable``/``=expression`` (mirroring
    ``seamm.Parameter.is_expr``/``.get()``), else return it unchanged."""
    if token is None:
        return token
    if (
        isinstance(token, str)
        and len(token) > 0
        and token[0] in ("$", "=")
        and token != "=="
    ):
        return str(eval(token[1:], context))  # noqa: S307 -- flowchart expression
    return token


def resolve_level(selected, context):
    """Dereference any ``$variable``/``=expression`` component of a level
    spec string, returning the resolved string.

    Needed because the ``model_chemistry`` parameter is one whole string
    (``[owner:]type@method[/basis[@cutoff]]``) -- SEAMM's own
    ``current_values_to_dict`` only substitutes a ``$var`` that is the
    *entire* parameter value, not one embedded inside a larger string like
    ``"DFT@$functional/def2-SVP"``. Each level-spec component (owner, type,
    method, basis, cutoff) is dereferenced separately here instead, so a
    preceding Loop step can vary any one of them -- most usefully type/method,
    typed into the GUI's Type/Method comboboxes, which now accept a
    ``$variable`` -- see ``TkModelChemistry``.

    Parameters
    ----------
    selected : str
        The (already whole-value-dereferenced) ``model_chemistry`` string.
    context : dict
        The flowchart-variables mapping to evaluate any expression against.

    Returns
    -------
    str
        `selected` unchanged if it does not parse as a level spec, or none
        of its components is an expression; otherwise the same level spec
        with every expression component evaluated and substituted.
    """
    try:
        parsed = parse_level(selected)
    except ValueError:
        return selected
    if not any(
        seamm.Node.is_expr(parsed[key])
        for key in ("owner", "type", "method", "basis", "cutoff")
    ):
        return selected
    owner = _dereference(parsed["owner"], context)
    type_ = _dereference(parsed["type"], context)
    method = _dereference(parsed["method"], context)
    basis = _dereference(parsed["basis"], context)
    cutoff = _dereference(parsed["cutoff"], context)
    level = _compose_theory(type_, method, basis, cutoff)
    return f"{owner}:{level}" if owner else level


def _accepts(function, name):
    """Whether ``function`` takes the keyword argument ``name``."""
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return False
    return name in parameters or any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values()
    )


def discover_model_chemistries(periodic_only=False, mdi_only=False, data_path=None):
    """Discover the model chemistries offered by the installed program steps.

    Each program plug-in (e.g. ``mopac_step``) may expose a
    ``get_model_chemistry_options()`` classmethod on its helper class. This
    method iterates the ``org.molssi.seamm`` Stevedore namespace, calls that
    method on every helper that defines it, and returns the union keyed by
    the canonical model-chemistry string.

    Parameters
    ----------
    periodic_only : bool
        Only return model chemistries validated for periodic systems.
    mdi_only : bool
        Only return model chemistries launchable via MDI.
    data_path : [pathlib.Path], optional
        Where a running flowchart finds data files (``Node.data_path``: a job's
        own ``data/`` directory, then the user's and the installation's), for the
        steps whose ``get_model_chemistry_options()`` takes it -- e.g. the
        Forcefield step, which offers the forcefields it finds there, so a job
        sees the ``local:`` and ``personal:`` forcefields sent with it.

    Returns
    -------
    dict
        Keyed by the advertised **level spec** ``[owner:]type@method``
        string. Each value is a ``_model_chemistry`` wrapper::

            {
                "level": key,                        # the level spec
                "owner": ..., "type": ..., "method": ...,  # parse_level(key)
                "basis": ..., "cutoff": ...,
                "step": "<stevedore plugin name>",   # resolution handle
                "options": { ... full get_model_chemistry_options() entry },
            }

        A program step advertises *level specs* only (it knows its levels
        of theory, not the task); the consuming step supplies the driver
        and task. See ``model_chemistry_naming.rst``.
    """
    result = {}
    mgr = stevedore.ExtensionManager(
        namespace="org.molssi.seamm",
        invoke_on_load=False,
        on_load_failure_callback=lambda m, ep, err: logger.warning(
            "Could not load step plug-in %r: %s", ep.name, err
        ),
    )
    for ext in mgr:
        getter = getattr(ext.plugin, "get_model_chemistry_options", None)
        if getter is None:
            continue
        kwargs = {"periodic_only": periodic_only, "mdi_only": mdi_only}
        if data_path is not None and _accepts(getter, "data_path"):
            kwargs["data_path"] = data_path
        try:
            options = getter(**kwargs)
        except Exception as e:
            logger.warning("%s.get_model_chemistry_options() failed: %s", ext.name, e)
            continue
        for option in options.values():
            key = option["model_chemistry"]
            if key in result:
                logger.warning(
                    "Model chemistry %s offered by more than one step; "
                    "keeping the one from '%s'.",
                    key,
                    result[key]["step"],
                )
                continue
            parsed = parse_level(key)
            result[key] = {
                "level": parsed["level"],
                "owner": parsed["owner"],
                "type": parsed["type"],
                "method": parsed["method"],
                "basis": parsed["basis"],
                "cutoff": parsed["cutoff"],
                "step": ext.name,
                "options": option,
            }
    return result


def match_model_chemistry(selected, available):
    """Match `selected` to an offered owner/type/method, ignoring the basis.

    Programs advertise only a few example basis sets, but the basis is the
    user's free choice. If a program offers the same owner/type/method as
    `selected`, return a ``_model_chemistry`` wrapper built from that offering
    with the user's basis/cutoff/level substituted; otherwise ``None``.
    """
    try:
        sel = parse_level(selected)
    except ValueError:
        return None
    for wrapper in available.values():
        if (
            wrapper["owner"] == sel["owner"]
            and wrapper["type"] == sel["type"]
            and wrapper["method"] == sel["method"]
        ):
            model_chemistry = dict(wrapper)
            model_chemistry["basis"] = sel["basis"]
            model_chemistry["cutoff"] = sel["cutoff"]
            model_chemistry["level"] = selected
            # The options are the offering's, but the basis an MDI engine is
            # launched with must be the user's, not the advertised example.
            options = dict(wrapper.get("options") or {})
            if options.get("mdi_basis_arg") is not None and sel["basis"]:
                options["mdi_basis_arg"] = sel["basis"]
            model_chemistry["options"] = options
            return model_chemistry
    return None


#: Model-chemistry types that were renamed, old -> new. A level with an old type
#: is accepted with a warning, as the new one, until flowcharts are converted:
#: ORCA's Hartree-Fock and MP2 are wavefunction (QC) methods (2026-10-12).
RENAMED_TYPES = {"HF": "QC", "MP2": "QC"}


def renamed_level(level):
    """The level with a renamed type replaced by its new name
    (``ORCA:HF@HF/def2-SVP`` -> ``ORCA:QC@HF/def2-SVP``), or None if its type
    was not renamed (or it does not parse)."""
    if not isinstance(level, str):
        return None
    try:
        parsed = parse_level(level)
    except ValueError:
        return None
    new = RENAMED_TYPES.get(parsed["type"])
    if new is None:
        return None
    prefix = f"{parsed['owner']}:" if parsed["owner"] else ""
    rest = level.strip()[len(prefix) + len(parsed["type"]) + 1 :]
    return f"{prefix}{new}@{rest}"


def availability_problem(selected, available, periodic=False):
    """Why a model chemistry is not available, or '' if it is.

    Shared by the step's run-time check and its parameters' rules, which the
    flowchart builder uses. A level with a renamed type (see
    :data:`RENAMED_TYPES`) is checked under its new name.
    """
    selected = renamed_level(selected) or selected
    if selected in available or match_model_chemistry(selected, available):
        return ""
    if len(available) == 0:
        return (
            f"The model chemistry '{selected}' is not available: no installed "
            "program plug-in offers a model chemistry"
            + (" for periodic systems." if periodic else ".")
        )
    return (
        f"The model chemistry '{selected}' is not available"
        + (" for periodic systems" if periodic else "")
        + ". The available model chemistries are: "
        + ", ".join(sorted(available))
        + "."
    )


class ModelChemistry(seamm.Node):
    """
    The non-graphical part of a Model Chemistry step in a flowchart.

    Attributes
    ----------
    parser : configargparse.ArgParser
        The parser object.

    options : tuple
        It contains a two item tuple containing the populated namespace and the
        list of remaining argument strings.

    parameters : ModelChemistryParameters
        The control parameters for Model Chemistry.

    See Also
    --------
    TkModelChemistry,
    ModelChemistry, ModelChemistryParameters
    """

    def __init__(
        self, flowchart=None, title="Model Chemistry", extension=None, logger=logger
    ):
        """A step for Model Chemistry in a SEAMM flowchart.

        You may wish to change the title above, which is the string displayed
        in the box representing the step in the flowchart.

        Parameters
        ----------
        flowchart: seamm.Flowchart
            The non-graphical flowchart that contains this step.

        title: str
            The name displayed in the flowchart.
        extension: None
            Not yet implemented
        logger : Logger = logger
            The logger to use and pass to parent classes

        Returns
        -------
        None
        """
        logger.debug(f"Creating Model Chemistry {self}")

        super().__init__(
            flowchart=flowchart,
            title="Model Chemistry",
            extension=extension,
            module=__name__,
            logger=logger,
        )  # yapf: disable

        self._metadata = model_chemistry_step.metadata
        self.parameters = model_chemistry_step.ModelChemistryParameters()

    @property
    def version(self):
        """The semantic version of this module."""
        return model_chemistry_step.__version__

    @property
    def git_revision(self):
        """The git version of this module."""
        return model_chemistry_step.__git_revision__

    def description_text(self, P=None):
        """Create the text description of what this step will do.
        The dictionary of control values is passed in as P so that
        the code can test values, etc.

        Parameters
        ----------
        P: dict
            An optional dictionary of the current values of the control
            parameters.
        Returns
        -------
        str
            A description of the current step.
        """
        if not P:
            P = self.parameters.values_to_dict()

        text = "Provide the model chemistry '{model_chemistry}' to subsequent steps"
        if P["periodic"] == "yes":
            text += ", considering only model chemistries that support periodic systems"
        text += "."

        return self.header + "\n" + __(text, **P, indent=4 * " ").__str__()

    def model_chemistries(self, periodic_only=False, mdi_only=False):
        """The model chemistries the installed program steps offer.

        See discover_model_chemistries(), which this calls.
        """
        return discover_model_chemistries(
            periodic_only=periodic_only,
            mdi_only=mdi_only,
            data_path=self._data_path(),
        )

    def _data_path(self):
        """The flowchart's data path, or None if it has none (e.g. in the editor)."""
        try:
            return self.data_path
        except Exception:
            return None

    def list_data_files(self):
        """The data files the selected model chemistry needs, such as a ``local:``
        or ``personal:`` forcefield, from the step that offers it
        (``model_chemistry_data_files()``), so they go with a submitted job."""
        selected = self.parameters["model_chemistry"].value
        if not isinstance(selected, str) or self.is_expr(selected):
            return []
        try:
            available = self.model_chemistries()
            model_chemistry = available.get(selected) or self._match_ignoring_basis(
                selected, available
            )
            if model_chemistry is None:
                return []
            provider = self.flowchart.plugin_manager.get(model_chemistry["step"])
        except Exception as e:
            logger.warning(f"Could not find the files for {selected}: {e}")
            return []
        getter = getattr(provider, "model_chemistry_data_files", None)
        if getter is None:
            return []
        return getter(model_chemistry, self)

    def _from_checkpoint(self, selected, checkpoint, available):
        """The model chemistry for an MLFF checkpoint given by path: described
        by the step that offers the program's MLFFs
        (``model_chemistry_for_checkpoint``), its method the file's name."""
        owner = parse_level(selected)["owner"]
        steps = {
            w["step"]
            for w in available.values()
            if w["type"] == "MLFF" and (owner is None or w["owner"] == owner)
        }
        if len(steps) != 1:
            raise ValueError(
                f"Cannot tell which program should use the checkpoint {checkpoint} "
                f"for '{selected}': "
                + (
                    "no installed step offers machine-learned forcefields"
                    + (f" from '{owner}'." if owner else ".")
                    if not steps
                    else f"several do ({', '.join(sorted(steps))}); name one."
                )
            )
        step = steps.pop()
        path = Path(checkpoint).expanduser()
        if not path.is_absolute():
            path = Path(self.flowchart.root_directory) / path
        provider = self.flowchart.plugin_manager.get(step)
        option = provider.model_chemistry_for_checkpoint(path)
        parsed = parse_level(option["model_chemistry"])
        printer.important(
            __(
                f"Using the checkpoint {path} as '{option['model_chemistry']}'.",
                indent=self.indent + 4 * " ",
            )
        )
        return {
            "level": parsed["level"],
            "owner": parsed["owner"],
            "type": parsed["type"],
            "method": parsed["method"],
            "basis": parsed["basis"],
            "cutoff": parsed["cutoff"],
            "step": step,
            "options": option,
        }

    def _match_ignoring_basis(self, selected, available):
        """See match_model_chemistry()."""
        return match_model_chemistry(selected, available)

    def run(self):
        """Run a Model Chemistry step.

        Parameters
        ----------
        None

        Returns
        -------
        seamm.Node
            The next node object in the flowchart.
        """
        next_node = super().run(printer)

        # Get the values of the parameters, dereferencing any variables
        P = self.parameters.current_values_to_dict(
            context=seamm.flowchart_variables._data
        )

        # Print what we are doing
        printer.important(__(self.description_text(P), indent=self.indent))

        periodic = P["periodic"] == "yes"
        selected = P["model_chemistry"]

        # Dereference any $variable/=expression embedded in one of the level
        # spec's components (owner/type/method/basis/cutoff) -- see
        # resolve_level's docstring for why this can't just be left to
        # current_values_to_dict above.
        resolved = resolve_level(selected, dict(seamm.flowchart_variables._data))
        if resolved != selected:
            printer.important(
                __(
                    f"Resolved the model chemistry to '{resolved}'.",
                    indent=self.indent + 4 * " ",
                )
            )
            selected = resolved

        # A type that has been renamed (HF@ and MP2@ are now QC@)
        renamed = renamed_level(selected)
        if renamed is not None:
            printer.important(
                __(
                    f"Warning: '{selected}' is the old name of '{renamed}'; please "
                    "update the flowchart, which will refuse the old name in future.",
                    indent=self.indent + 4 * " ",
                )
            )
            selected = renamed

        # Discover what the installed program plug-ins offer, then validate the
        # selection against it before publishing it for downstream steps.
        available = self.model_chemistries(periodic_only=periodic, mdi_only=False)
        checkpoint = str(P.get("checkpoint", "") or "").strip()
        is_mlff = self.parameters._is_mlff(selected)
        if checkpoint and is_mlff:
            model_chemistry = self._from_checkpoint(selected, checkpoint, available)
        elif selected in available:
            model_chemistry = available[selected]
        else:
            # The exact string is not advertised, but the basis is a free choice
            # (a program advertises only a few example bases; the user may pick
            # any, e.g. from the Basis Set Exchange). Accept the selection if a
            # program offers the same owner/type/method, publishing the user's
            # basis and cutoff.
            model_chemistry = self._match_ignoring_basis(selected, available)
            if model_chemistry is None:
                raise ValueError(
                    availability_problem(selected, available, periodic=periodic)
                )

        # The MLFF engine's options for this run (e.g. --eeq-reuse)
        engine_options = str(P.get("engine options", "") or "").strip()
        if engine_options and model_chemistry.get("type") == "MLFF":
            model_chemistry = dict(model_chemistry)
            model_chemistry["options"] = dict(model_chemistry.get("options") or {})
            model_chemistry["options"]["engine_args"] = shlex.split(engine_options)
            printer.important(
                __(
                    f"The engine will be run with the options: {engine_options}",
                    indent=self.indent + 4 * " ",
                )
            )

        # Publish it as a workspace variable for downstream steps (e.g. LAMMPS),
        # mirroring how the Forcefield step provides "_forcefield".
        self.set_variable("_model_chemistry", model_chemistry)

        logger.debug("Stored _model_chemistry:\n%s", pprint.pformat(model_chemistry))

        return next_node

    def analyze(self, indent="", **kwargs):
        """Do any analysis of the output from this step.

        Also print important results to the local step.out file using
        "printer".

        Parameters
        ----------
        indent: str
            An extra indentation for the output
        """
        printer.normal(
            __(
                "This is a placeholder for the results from the Model Chemistry step",
                indent=4 * " ",
                wrap=True,
                dedent=False,
            )
        )
