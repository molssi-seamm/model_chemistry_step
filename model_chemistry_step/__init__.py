# -*- coding: utf-8 -*-

"""
model_chemistry_step
A SEAMM plug-in for defining the model chemistry for subsequent steps
"""

# Bring up the classes so that they appear to be directly in
# the model_chemistry_step package.

from .model_chemistry import ModelChemistry  # noqa: F401, E501
from .model_chemistry_parameters import ModelChemistryParameters  # noqa: F401, E501
from .model_chemistry_step import ModelChemistryStep  # noqa: F401, E501
from .tk_model_chemistry import TkModelChemistry  # noqa: F401, E501

from .metadata import metadata  # noqa: F401

# Handle versioneer
from ._version import get_versions

__author__ = "Paul Saxe"
__email__ = "psaxe@molssi.org"
versions = get_versions()
__version__ = versions["version"]
__git_revision__ = versions["full-revisionid"]
del get_versions, versions
