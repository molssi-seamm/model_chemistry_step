# -*- coding: utf-8 -*-

"""The graphical part of a Model Chemistry step.

The step persists a single **level spec** (``[owner:]type@method[/basis
[@cutoff]]``) in the ``model_chemistry`` parameter -- the level of theory, with
no driver or task (those belong to the consuming step). The dialog presents it
two ways, toggled by a checkbox:

* **Guided (default)** -- a cascading set of selectors, **Type -> Method ->
  Program** (where Program is the PES *owner*), plus a Basis field, plus a
  periodic-system filter:

  * on open, the stored level spec is decomposed (``parse_level``) to preset
    the three selectors;
  * the choices are discovered live from the installed program steps
    (``node.model_chemistries(...)``), narrowed by the periodic filter;
  * Type narrows Method narrows Program; Program auto-selects when only one
    program implements the chosen ``type@method``;
  * on *OK*, the discovered level spec matching the three selections is
    composed and stored back into the ``model_chemistry`` parameter.
  * Type/Method/Program also accept typed text, including a ``$variable``/
    ``=expression`` (see ``ModelChemistry.resolve_level``), for driving the
    model chemistry from a preceding Loop step.

* **Direct entry** -- one plain text field bound straight to the
  ``model_chemistry`` parameter, for typing the whole canonical string (or a
  single ``$variable`` standing for it) by hand -- the simplest way to use a
  variable, since it sidesteps the picker's discovery/validation machinery
  entirely. The dialog switches to this mode automatically when the stored
  value cannot be decomposed by the picker (an expression, or a string the
  grammar can't parse).
"""

import logging
import tkinter as tk
import tkinter.ttk as ttk

import seamm
import seamm_widgets as sw

from .grammar import parse_level

logger = logging.getLogger(__name__)


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

        A checkbox switches between that guided picker and typing the whole
        ``model_chemistry`` string directly -- much the simplest way to use a
        ``$variable`` (either for the whole level, or embedded in it), since
        it sidesteps the picker's discovery/validation entirely. The direct-
        entry field is the real ``model_chemistry`` parameter's own widget
        (a plain text entry), so the base class captures it on *OK* the same
        way it does ``periodic`` -- :meth:`handle_dialog` only needs to keep
        it in sync with the picker's composed value when direct entry is off.

        See Also
        --------
        TkModelChemistry.reset_dialog
        """

        frame = super().create_dialog(title="Model Chemistry")
        P = self.node.parameters

        # The periodic filter -- a real parameter, so it is saved automatically.
        self["periodic"] = P["periodic"].widget(frame)
        self["periodic"].config(state="readonly")

        # GUI-only toggle between the guided picker and typing the whole
        # string directly.
        self._direct_entry_var = tk.BooleanVar(value=False)
        self["direct entry"] = ttk.Checkbutton(
            frame,
            text="Enter the model chemistry directly as text",
            variable=self._direct_entry_var,
            command=self._direct_entry_changed,
        )

        # The direct-entry field -- a real parameter widget (LabeledEntry, since
        # 'model_chemistry' is a plain string parameter), so the base class
        # captures it on OK just like 'periodic'.
        self["model_chemistry"] = P["model_chemistry"].widget(frame, width=50)

        # The cascading selectors (GUI-only; not bound to a parameter).
        # 'normal' (not 'readonly') so a $variable/=expression can be typed
        # in -- e.g. to vary the type/method/program from a preceding Loop,
        # dereferenced at run time by ModelChemistry.run() -- while still
        # offering the discovered choices via the dropdown.
        self["type"] = sw.LabeledCombobox(frame, labeltext="Type:", state="normal")
        self["method"] = sw.LabeledCombobox(frame, labeltext="Method:", state="normal")
        self["program"] = sw.LabeledCombobox(
            frame, labeltext="Program:", state="normal"
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
        """Lay out the widgets: the periodic filter, the direct-entry toggle,
        then either the direct-entry text field or the Type/Method/Program(
        /Basis) cascade, depending on the toggle.

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
        self["periodic"].grid(row=row, column=0, sticky=tk.EW)
        row += 1
        self["direct entry"].grid(row=row, column=0, sticky=tk.W)
        row += 1

        if self._direct_entry_var.get():
            self["model_chemistry"].grid(row=row, column=0, sticky=tk.EW)
            shown = ["periodic", "model_chemistry"]
            row += 1
        else:
            shown = ["periodic", "type", "method", "program"]
            for key in ("type", "method", "program"):
                self[key].grid(row=row, column=0, sticky=tk.EW)
                row += 1

            # Show the basis only for a level of theory that uses one --
            # unknowable by discovery when type/method is a $variable, so
            # default to showing it.
            type_, method = self["type"].get(), self["method"].get()
            if (
                self.is_expr(type_)
                or self.is_expr(method)
                or self._needs_basis(type_, method, self["program"].get())
            ):
                self["basis"].grid(row=row, column=0, sticky=tk.EW)
                shown.append("basis")
                row += 1

        sw.align_labels([self[key] for key in shown], sticky=tk.E)

        return row

    def _compose_from_picker(self):
        """Compose the canonical level-spec string from the current Type/
        Method/Program/Basis selections, plus the basis picker's remembered
        element selection (for reconstructing the '...' dialog on reopen).

        Returns
        -------
        (str, str)
            ``(level, elements)``; ``("", "")`` if the selectors are not yet
            a complete Type+Method+Program selection.
        """
        type_ = self["type"].get()
        method = self["method"].get()
        program = self["program"].get()
        if not (type_ and method and program):
            return "", ""
        # The owner/type/method must be one a program offers (run() validates
        # this); the basis is the user's free choice. Whether a basis applies
        # cannot be discovered when type/method is a $variable, so include
        # whatever basis is entered in that case too.
        level = f"{program}:{type_}@{method}"
        elements = ""
        if (
            self.is_expr(type_)
            or self.is_expr(method)
            or self._needs_basis(type_, method, program)
        ):
            basis = self["basis"].get_name().strip()
            if basis:
                level += f"/{basis}"
                elements = ",".join(self["basis"].get()["elements"])
        return level, elements

    def _direct_entry_changed(self):
        """The direct-entry checkbox was toggled: hand off the current value
        between the text field and the picker (best-effort in each direction,
        so nothing already entered is silently lost), then re-lay-out."""
        if self._direct_entry_var.get():
            # Picker -> text: seed the field with whatever the picker
            # currently composes (leave the field as-is if the picker has no
            # complete/valid selection to offer).
            level, _ = self._compose_from_picker()
            if level:
                self["model_chemistry"].set(level)
        else:
            # Text -> picker: decompose it the same way reopening the dialog
            # does; falls back to the first available choice if it doesn't
            # parse (e.g. it's a whole-string $variable).
            self._discover()
            self._cascade(*self._decompose(self["model_chemistry"].get()))

        self.reset_dialog()

    def handle_dialog(self, result):
        """On *OK*, store the value that should be kept -- the typed text
        as-is in direct-entry mode, or the string composed from the Type/
        Method/Program/Basis selectors otherwise -- into the
        ``model_chemistry`` parameter, keeping its widget in sync (so a
        reopened dialog, or the base class's own widget-capture pass in
        :meth:`seamm.TkNode.handle_dialog`, sees the same value).

        Parameters
        ----------
        result : str
            The button that closed the dialog (``"OK"``, ``"Cancel"``, ...).
        """
        if result == "OK":
            if self._direct_entry_var.get():
                # Whatever the user typed, verbatim -- nothing reconstructs a
                # picker selection from free text.
                text = self["model_chemistry"].get().strip()
                self.node.parameters["model_chemistry"].value = text
                self.node.parameters["basis elements"].value = ""
            else:
                level, elements = self._compose_from_picker()
                if level:
                    self["model_chemistry"].set(level)
                    self.node.parameters["model_chemistry"].value = level
                    self.node.parameters["basis elements"].value = elements
                # else: selectors incomplete -- leave the stored parameter
                # (and its widget) at whatever it was loaded with.

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
        and the layout refreshed so it shows only when the level uses a basis.

        A ``$variable``/``=expression`` value (see `is_expr`) is left exactly
        as typed at every step here -- it cannot be discovered/validated
        against the installed program plug-ins (its value is not known until
        run time), so it must not be silently replaced by "the first
        available choice" the way an unrecognized plain string would be.
        """
        types = self._types()
        self["type"].combobox.configure(values=types)
        if type_ not in types and not self.is_expr(type_):
            type_ = types[0] if types else ""
        self["type"].set(type_)

        methods = [] if self.is_expr(type_) else self._methods(type_)
        self["method"].combobox.configure(values=methods)
        if method not in methods and not self.is_expr(method):
            method = methods[0] if methods else ""
        self["method"].set(method)

        programs = (
            []
            if self.is_expr(type_) or self.is_expr(method)
            else self._programs(type_, method)
        )
        self["program"].combobox.configure(values=programs)
        if program not in programs and not self.is_expr(program):
            program = programs[0] if programs else ""
        self["program"].set(program)

        # Seed the basis: the caller's value (e.g. the stored one) wins, else the
        # program's advertised default for this level. Whether a level "needs" a
        # basis cannot be discovered when type/method is a variable -- default to
        # showing the field in that case (most levels of theory use one, and the
        # basis field itself accepts a $variable/blank either way).
        if (
            self.is_expr(type_)
            or self.is_expr(method)
            or self._needs_basis(type_, method, program)
        ):
            self["basis"].set(basis or self._default_basis(type_, method, program))
        else:
            self["basis"].set("")
        self.reset_dialog()

    def _decompose(self, selected):
        """Return ``(type_, method, program, basis)`` decomposed from
        `selected`, or all-``None`` if it is an expression (see `is_expr`) or
        does not parse as a level spec (see `parse_level`) -- the picker has
        nothing to preset from in either case."""
        if isinstance(selected, str) and not self.is_expr(selected):
            try:
                components = parse_level(selected)
            except ValueError:
                pass
            else:
                return (
                    components["type"],
                    components["method"],
                    components["owner"],
                    components["basis"],
                )
        return None, None, None, None

    def _load_from_parameter(self):
        """Preset the dialog from the stored canonical string.

        The direct-entry field always gets the raw stored value. The picker
        gets it decomposed when possible (`_decompose`); dialog opens in
        direct-entry mode when it is not (a non-empty string the picker
        cannot represent -- a ``$variable``, or one the grammar can't parse)
        since the picker would otherwise silently show unrelated defaults.
        """
        selected = self.node.parameters["model_chemistry"].value
        self["model_chemistry"].set(selected if isinstance(selected, str) else "")

        type_, method, program, basis = self._decompose(selected)
        self._direct_entry_var.set(
            type_ is None and isinstance(selected, str) and selected != ""
        )

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
