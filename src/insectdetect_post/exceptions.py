"""Custom exceptions for the insect-detect-post modules.

Source:   https://github.com/maxsitt/insect-detect-post
License:  GNU AGPLv3 (https://choosealicense.com/licenses/agpl-3.0/)
Author:   Maximilian Sittinger (https://github.com/maxsitt)
Docs:     https://maxsitt.github.io/insect-detect-docs/

Classes:
    PipelineCancelled: Raised when the user requests cancellation of a pipeline or inspection run.
"""

from __future__ import annotations


class PipelineCancelled(Exception):
    """Raised when the user requests cancellation of a pipeline or inspection run."""
