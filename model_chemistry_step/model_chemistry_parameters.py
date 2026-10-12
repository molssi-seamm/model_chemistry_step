# -*- coding: utf-8 -*-
"""
Control parameters for the Model Chemistry step in a SEAMM flowchart
"""

import logging
import seamm
import pprint  # noqa: F401

logger = logging.getLogger(__name__)


class ModelChemistryParameters(seamm.Parameters):
    """
    The control parameters for Model Chemistry.

    You need to replace the "time" entry in dictionary below these comments with the
    definitions of parameters to control this step. The keys are parameters for the
    current plugin,the values are dictionaries as outlined below.

    Examples
    --------
    ::

        parameters = {
            "time": {
                "default": 100.0,
                "kind": "float",
                "default_units": "ps",
                "enumeration": tuple(),
                "format_string": ".1f",
                "description": "Simulation time:",
                "help_text": ("The time to simulate in the dynamics run.")
            },
        }

    parameters : {str: {str: str}}
        A dictionary containing the parameters for the current step.
        Each key of the dictionary is a dictionary that contains the
        the following keys:

    parameters["default"] :
        The default value of the parameter, used to reset it.

    parameters["kind"] : enum()
        Specifies the kind of a variable. One of  "integer", "float", "string",
        "boolean", or "enum"

        While the "kind" of a variable might be a numeric value, it may still have
        enumerated custom values meaningful to the user. For instance, if the parameter
        is a convergence criterion for an optimizer, custom values like "normal",
        "precise", etc, might be adequate. In addition, any parameter can be set to a
        variable of expression, indicated by having "$" as the first character in the
        field. For example, $OPTIMIZER_CONV.

    parameters["default_units"] : str
        The default units, used for resetting the value.

    parameters["enumeration"] : tuple
        A tuple of enumerated values.

    parameters["format_string"] : str
        A format string for "pretty" output.

    parameters["description"] : str
        A short string used as a prompt in the GUI.

    parameters["help_text"] : str
        A longer string to display as help for the user.

    See Also
    --------
    ModelChemistry, TkModelChemistry, ModelChemistryParameters, Model ChemistryStep
    """

    parameters = {
        "model_chemistry": {
            "default": "MOPAC:SQM@PM6-ORG",
            "kind": "string",
            "default_units": "",
            "enumeration": tuple(),
            "format_string": "",
            "description": "Model chemistry:",
            "help_text": (
                "The model chemistry to provide to subsequent steps, given as "
                "the canonical string 'Program:Type@Method[/Basis[@Cutoff]]'. "
                "The available choices are discovered from the installed program "
                "plug-ins."
            ),
        },
        "periodic": {
            "default": "no",
            "kind": "enum",
            "default_units": "",
            "enumeration": ("yes", "no"),
            "format_string": "s",
            "description": "Periodic system:",
            "help_text": (
                "Whether the model chemistry must support periodic systems. If "
                "'yes', only model chemistries validated for periodic systems "
                "are offered."
            ),
        },
        "basis elements": {
            "default": "",
            "kind": "string",
            "default_units": "",
            "enumeration": tuple(),
            "format_string": "",
            "description": "Basis elements:",
            "help_text": (
                "GUI-only: the elements (comma-separated symbols) last selected "
                "in the basis-set picker, remembered so the picker can be "
                "reconstructed. Not used when running; the basis itself is part "
                "of the model-chemistry string."
            ),
        },
        "checkpoint": {
            "default": "",
            "kind": "string",
            "default_units": "",
            "enumeration": tuple(),
            "format_string": "",
            "description": "Checkpoint:",
            "help_text": (
                "For a machine-learned forcefield (MLFF): the model's checkpoint "
                "file, to use it rather than a model found in the model "
                "directories -- e.g. one written during training. A path, "
                "relative to the job's directory unless absolute, or a "
                "$variable. Empty uses the model chosen above."
            ),
        },
        "engine options": {
            "default": "",
            "kind": "string",
            "default_units": "",
            "enumeration": tuple(),
            "format_string": "",
            "description": "Engine options:",
            "help_text": (
                "For a machine-learned forcefield (MLFF): options for its engine "
                "in this run, e.g. '--eeq-reuse' or "
                "'--dispersion \"{regime: large}\"' for xnn."
            ),
        },
        # # Results handling ... uncomment if needed
        # "results": {
        #     "default": {},
        #     "kind": "dictionary",
        #     "default_units": "",
        #     "enumeration": tuple(),
        #     "format_string": "",
        #     "description": "results",
        #     "help_text": "The results to save to variables or in tables.",
        # },
    }

    # Rules shared by the dialog and the flowchart builder (see seamm.Parameters)

    #: Parameters that apply only to a machine-learned forcefield
    MLFF_ONLY = ("checkpoint", "engine options")

    def _is_mlff(self, selected):
        """Whether the model chemistry is an MLFF (or a $variable, which might
        be)."""
        from .grammar import parse_level

        if not isinstance(selected, str) or selected.strip() == "":
            return False
        if self._is_expr(selected):
            return True
        try:
            return parse_level(selected)["type"] == "MLFF"
        except ValueError:
            return False

    def applies(self, key, values=None, _seen=None):
        """The checkpoint and engine options apply only to an MLFF."""
        if values is None:
            values = self.current_values()
        if not super().applies(key, values, _seen):
            return False
        if key in self.MLFF_ONLY:
            return self._is_mlff(values.get("model_chemistry"))
        return True

    def not_applicable_reason(self, key, values=None):
        if values is None:
            values = self.current_values()
        if key in self.MLFF_ONLY and not self._is_mlff(values.get("model_chemistry")):
            return "it is only for a machine-learned forcefield (MLFF)"
        return super().not_applicable_reason(key, values)

    def problems(self, values=None):
        """The model chemistry must be one the installed programs offer (the basis
        is a free choice), as the step checks when it runs."""
        from .model_chemistry import availability_problem, discover_model_chemistries

        if values is None:
            values = self.current_values()
        result = super().problems(values)
        selected = values.get("model_chemistry")
        if not isinstance(selected, str) or selected.strip() == "":
            return result
        if self._is_expr(selected):
            return result  # resolved when the flowchart runs
        if self._is_mlff(selected) and str(values.get("checkpoint", "")).strip():
            return result  # a checkpoint by path is checked when it runs
        periodic = str(values.get("periodic", "no")).lower() == "yes"
        key = (periodic,)
        cache = ModelChemistryParameters._available
        if key not in cache:
            cache[key] = discover_model_chemistries(periodic_only=periodic)
        problem = availability_problem(selected, cache[key], periodic=periodic)
        if problem:
            result.append(problem)
        return result

    _available = {}  # discovered model chemistries, by (periodic,)

    def __init__(self, defaults={}, data=None):
        """
        Initialize the parameters, by default with the parameters defined above

        Parameters
        ----------
        defaults: dict
            A dictionary of parameters to initialize. The parameters
            above are used first and any given will override/add to them.
        data: dict
            A dictionary of keys and a subdictionary with value and units
            for updating the current, default values.

        Returns
        -------
        None
        """

        logger.debug("ModelChemistryParameters.__init__")

        super().__init__(
            defaults={**ModelChemistryParameters.parameters, **defaults}, data=data
        )
