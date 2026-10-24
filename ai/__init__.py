"""
Root alias package for src.ai.
Enables importing directly from 'ai' as well as 'src.ai'.
"""
import sys
from src import ai as _src_ai

# Re-export all public symbols from src.ai
for _attr in _src_ai.__all__:
    globals()[_attr] = getattr(_src_ai, _attr)

__all__ = _src_ai.__all__
