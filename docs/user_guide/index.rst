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


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
