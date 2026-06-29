# -*- coding: utf-8 -*-

"""Non-graphical part of the Model Chemistry step in a SEAMM flowchart"""

import logging
import importlib.resources
import pprint

import model_chemistry_step
import molsystem
import seamm
from seamm_util import ureg, Q_  # noqa: F401
import seamm_util.printing as printing
from seamm_util.printing import FormattedText as __
import stevedore

from .grammar import parse_level

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
            try:
                options = getter(periodic_only=periodic_only, mdi_only=mdi_only)
            except Exception as e:
                logger.warning(
                    "%s.get_model_chemistry_options() failed: %s", ext.name, e
                )
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

    def _match_ignoring_basis(self, selected, available):
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
                return model_chemistry
        return None

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

        # Discover what the installed program plug-ins offer, then validate the
        # selection against it before publishing it for downstream steps.
        available = self.model_chemistries(periodic_only=periodic, mdi_only=False)
        if selected in available:
            model_chemistry = available[selected]
        else:
            # The exact string is not advertised, but the basis is a free choice
            # (a program advertises only a few example bases; the user may pick
            # any, e.g. from the Basis Set Exchange). Accept the selection if a
            # program offers the same owner/type/method, publishing the user's
            # basis and cutoff.
            model_chemistry = self._match_ignoring_basis(selected, available)
            if model_chemistry is None:
                if len(available) == 0:
                    raise ValueError(
                        f"The model chemistry '{selected}' is not available: no "
                        "installed program plug-in offers a model chemistry"
                        + (" for periodic systems." if periodic else ".")
                    )
                raise ValueError(
                    f"The model chemistry '{selected}' is not available"
                    + (" for periodic systems" if periodic else "")
                    + ". The available model chemistries are: "
                    + ", ".join(sorted(available))
                    + "."
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
