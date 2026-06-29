# -*- coding: utf-8 -*-

"""The graphical part of a Model Chemistry step.

The step persists a single **level spec** (``[owner:]type@method[/basis
[@cutoff]]``) in the ``model_chemistry`` parameter -- the level of theory, with
no driver or task (those belong to the consuming step). The dialog presents it
as a cascading set of selectors -- **Type -> Method -> Program** (where Program
is the PES *owner*) -- plus a periodic-system filter:

* on open, the stored level spec is decomposed (``parse_level``) to preset the
  three selectors;
* the choices are discovered live from the installed program steps
  (``node.model_chemistries(...)``), narrowed by the periodic filter;
* Type narrows Method narrows Program; Program auto-selects when only one
  program implements the chosen ``type@method``;
* on *OK*, the discovered level spec matching the three selections is stored
  back into the ``model_chemistry`` parameter.
"""

import logging
import tkinter as tk

import seamm
import seamm_widgets as sw

from .grammar import parse_level

logger = logging.getLogger(__name__)

_CASCADE = ("periodic", "type", "method", "program")


class TkModelChemistry(seamm.TkNode):
    """
    The graphical part of a Model Chemistry step in a flowchart.

    Attributes
    ----------
    tk_flowchart : TkFlowchart = None
        The flowchart that we belong to.
    node : Node = None
        The corresponding node of the non-graphical flowchart
    namespace : str
        The namespace of the current step.
    canvas: tkCanvas = None
        The Tk Canvas to draw on
    dialog : Dialog
        The Pmw dialog object
    x : int = None
        The x-coordinate of the center of the picture of the node
    y : int = None
        The y-coordinate of the center of the picture of the node
    w : int = 200
        The width in pixels of the picture of the node
    h : int = 50
        The height in pixels of the picture of the node
    self[widget] : dict
        A dictionary of tk widgets built using the information
        contained in Model Chemistry_parameters.py

    See Also
    --------
    ModelChemistry, TkModelChemistry,
    ModelChemistryParameters,
    """

    def __init__(
        self,
        tk_flowchart=None,
        node=None,
        canvas=None,
        x=None,
        y=None,
        w=200,
        h=50,
    ):
        """
        Initialize a graphical node.

        Parameters
        ----------
        tk_flowchart: Tk_Flowchart
            The graphical flowchart that we are in.
        node: Node
            The non-graphical node for this step.
        canvas: Canvas
           The Tk canvas to draw on.
        x: float
            The x position of the nodes center on the canvas.
        y: float
            The y position of the nodes cetner on the canvas.
        w: float
            The nodes graphical width, in pixels.
        h: float
            The nodes graphical height, in pixels.

        Returns
        -------
        None
        """
        self.dialog = None

        # The model chemistries discovered for the current periodic filter,
        # keyed by canonical string (refreshed when the filter changes).
        self._model_chemistries = {}

        super().__init__(
            tk_flowchart=tk_flowchart,
            node=node,
            canvas=canvas,
            x=x,
            y=y,
            w=w,
            h=h,
        )

    def create_dialog(self):
        """Create the dialog for editing the Model Chemistry step.

        The periodic filter is a normal parameter widget, so the base class
        captures it on *OK*. Type/Method/Program are GUI-only comboboxes; the
        canonical ``model_chemistry`` string is composed from them in
        :meth:`handle_dialog`.

        See Also
        --------
        TkModelChemistry.reset_dialog
        """

        frame = super().create_dialog(title="Model Chemistry")
        P = self.node.parameters

        # The periodic filter -- a real parameter, so it is saved automatically.
        self["periodic"] = P["periodic"].widget(frame)
        self["periodic"].config(state="readonly")

        # The cascading selectors (GUI-only; not bound to a parameter).
        self["type"] = sw.LabeledCombobox(frame, labeltext="Type:", state="readonly")
        self["method"] = sw.LabeledCombobox(
            frame, labeltext="Method:", state="readonly"
        )
        self["program"] = sw.LabeledCombobox(
            frame, labeltext="Program:", state="readonly"
        )
        # The basis set -- a shared widget (entry/list + '...' to the Basis Set
        # Exchange). Shown only for levels of theory that use a basis (HF, DFT,
        # MP2, coupled cluster); hidden for SQM/FF/MLFF.
        self["basis"] = sw.BasisSetField(frame, labeltext="Basis set:")
        self["basis"].elements_callback = self._current_elements

        # Changing the filter re-discovers; changing a level cascades downward.
        self["periodic"].combobox.bind("<<ComboboxSelected>>", self._filter_changed)
        self["type"].combobox.bind("<<ComboboxSelected>>", self._type_changed)
        self["method"].combobox.bind("<<ComboboxSelected>>", self._method_changed)
        self["program"].combobox.bind("<<ComboboxSelected>>", self._program_changed)

        self.reset_dialog()

    def edit(self):
        """Present the dialog, presetting the selectors from the stored value."""
        if self.dialog is None:
            self.create_dialog()

        self._load_from_parameter()
        self.reset_dialog()
        self.fit_dialog()

        super().edit()

    def reset_dialog(self, widget=None):
        """Lay out the widgets: the periodic filter, then Type/Method/Program.

        Parameters
        ----------
        widget : Tk Widget = None

        See Also
        --------
        TkModelChemistry.create_dialog
        """
        frame = self["frame"]
        for slave in frame.grid_slaves():
            slave.grid_forget()

        row = 0
        for key in _CASCADE:
            self[key].grid(row=row, column=0, sticky=tk.EW)
            row += 1

        shown = list(_CASCADE)
        # Show the basis only for a level of theory that uses one.
        if self._needs_basis(
            self["type"].get(), self["method"].get(), self["program"].get()
        ):
            self["basis"].grid(row=row, column=0, sticky=tk.EW)
            shown.append("basis")
            row += 1

        sw.align_labels([self[key] for key in shown], sticky=tk.E)

        return row

    def handle_dialog(self, result):
        """On *OK*, compose the canonical model-chemistry string from the
        Type/Method/Program selectors and store it in the ``model_chemistry``
        parameter before the base class captures the periodic filter.

        Parameters
        ----------
        result : str
            The button that closed the dialog (``"OK"``, ``"Cancel"``, ...).
        """
        if result == "OK":
            type_ = self["type"].get()
            method = self["method"].get()
            program = self["program"].get()
            if type_ and method and program:
                # Compose the level spec from the selectors plus the chosen basis.
                # The owner/type/method must be one a program offers (run()
                # validates this); the basis is the user's free choice.
                level = f"{program}:{type_}@{method}"
                elements = ""
                if self._needs_basis(type_, method, program):
                    basis = self["basis"].get_name().strip()
                    if basis:
                        level += f"/{basis}"
                        # Remember the picker's element selection so it can be
                        # reconstructed on reopen (GUI-only; not used in run()).
                        elements = ",".join(self["basis"].get()["elements"])
                self.node.parameters["model_chemistry"].value = level
                self.node.parameters["basis elements"].value = elements

        super().handle_dialog(result)

    # ----------------------------------------------------------------- #
    # Discovery + cascade helpers
    # ----------------------------------------------------------------- #

    def _discover(self):
        """Refresh the discovered model chemistries for the current filter."""
        periodic = self["periodic"].get() == "yes"
        self._model_chemistries = self.node.model_chemistries(periodic_only=periodic)

    def _types(self):
        return sorted({w["type"] for w in self._model_chemistries.values()})

    def _methods(self, type_):
        return sorted(
            {
                w["method"]
                for w in self._model_chemistries.values()
                if w["type"] == type_
            }
        )

    def _programs(self, type_, method):
        return sorted(
            {
                w["owner"]
                for w in self._model_chemistries.values()
                if w["type"] == type_ and w["method"] == method
            }
        )

    def _needs_basis(self, type_, method, program):
        """Whether the offered level of theory uses a basis (data-driven: any
        matching discovered option carries one)."""
        return bool(self._default_basis(type_, method, program))

    def _default_basis(self, type_, method, program):
        """An example basis a program advertises for this owner/type/method, or
        ``""`` if it uses none."""
        for w in self._model_chemistries.values():
            if (
                w["type"] == type_
                and w["method"] == method
                and (not program or w["owner"] == program)
                and w.get("basis")
            ):
                return w["basis"]
        return ""

    def _current_elements(self):
        """Element symbols in the current configuration, to preselect in the
        Basis Set Exchange dialog. Best-effort: empty if there is none yet."""
        try:
            _, configuration = self.node.get_system_configuration(None)
            return sorted(set(configuration.atoms.symbols))
        except Exception:
            return []

    def _cascade(self, type_=None, method=None, program=None, basis=None):
        """Repopulate the three comboboxes, keeping valid selections and
        falling back to the first available choice when one is no longer
        valid (so each level always has a consistent selection below it). The
        basis field is seeded with the advertised default (or the passed value)
        and the layout refreshed so it shows only when the level uses a basis."""
        types = self._types()
        self["type"].combobox.configure(values=types)
        if type_ not in types:
            type_ = types[0] if types else ""
        self["type"].set(type_)

        methods = self._methods(type_)
        self["method"].combobox.configure(values=methods)
        if method not in methods:
            method = methods[0] if methods else ""
        self["method"].set(method)

        programs = self._programs(type_, method)
        self["program"].combobox.configure(values=programs)
        if program not in programs:
            program = programs[0] if programs else ""
        self["program"].set(program)

        # Seed the basis: the caller's value (e.g. the stored one) wins, else the
        # program's advertised default for this level.
        if self._needs_basis(type_, method, program):
            self["basis"].set(basis or self._default_basis(type_, method, program))
        else:
            self["basis"].set("")
        self.reset_dialog()

    def _load_from_parameter(self):
        """Preset the selectors by decomposing the stored canonical string."""
        selected = self.node.parameters["model_chemistry"].value
        type_ = method = program = basis = None
        if isinstance(selected, str) and not self.is_expr(selected):
            try:
                components = parse_level(selected)
            except ValueError:
                pass
            else:
                type_ = components["type"]
                method = components["method"]
                program = components["owner"]
                basis = components["basis"]

        self._discover()
        self._cascade(type_, method, program, basis)

        # Restore the picker's remembered element selection (set by _cascade's
        # set() to []), so reopening the '...' dialog reconstructs the case.
        elements = self.node.parameters["basis elements"].value
        if elements:
            current = self["basis"].get_name()
            self["basis"].set({"name": current, "elements": elements.split(",")})

    def _filter_changed(self, event=None):
        """The periodic filter changed: re-discover, keeping selections (and the
        basis) if they survive the new filter."""
        self._discover()
        self._cascade(
            self["type"].get(),
            self["method"].get(),
            self["program"].get(),
            self["basis"].get(),
        )

    def _type_changed(self, event=None):
        """Type changed: reset Method, Program, and basis to the first available."""
        self._cascade(self["type"].get(), None, None)

    def _method_changed(self, event=None):
        """Method changed: reset Program and basis to the first available."""
        self._cascade(self["type"].get(), self["method"].get(), None)

    def _program_changed(self, event=None):
        """Program changed: refresh the advertised default basis for it."""
        self._cascade(self["type"].get(), self["method"].get(), self["program"].get())

    def right_click(self, event):
        """
        Handles the right click event on the node.

        Parameters
        ----------
        event : Tk Event

        Returns
        -------
        None

        See Also
        --------
        TkModelChemistry.edit
        """

        super().right_click(event)
        self.popup_menu.add_command(label="Edit..", command=self.edit)

        self.popup_menu.tk_popup(event.x_root, event.y_root, 0)
