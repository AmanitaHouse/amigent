"""Create the metadata directory before setuptools asks for it.

``egg_base`` has to exist already. It lives under ``build/``, the repository's
generated-output root, so an editable install does not write ``*.egg-info``
beside the package sources.
"""

from pathlib import Path

from setuptools import setup

Path("build/egg-info").mkdir(parents=True, exist_ok=True)
setup()
