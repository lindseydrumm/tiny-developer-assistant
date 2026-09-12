"""Structured code analysis backed by an LLM.

Layering (see CONSTITUTION.md section III):

    interface/  ->  core.analyzer  ->  core.llm_client  ->  provider SDK
                         |                    |
                         +---- core.prompts --+

Dependencies point in one direction only. ``core`` never imports from
``interface``.
"""

__version__ = "0.1.0"
