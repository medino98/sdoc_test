"""
StrictDoc project configuration.

Replaces the deprecated strictdoc.toml format (StrictDoc >= 0.27).
StrictDoc calls create_config() to obtain the project settings.

This file must live at the project root: StrictDoc only looks for
strictdoc_config.py in the directory passed to `export`/`server`.
"""

from strictdoc.core.project_config import ProjectConfig


def create_config() -> ProjectConfig:
    return ProjectConfig(
        project_title="LVGL Safe PoC",
        project_features=[
            # Stable features.
            "TABLE_SCREEN",
            "TRACEABILITY_SCREEN",
            "DEEP_TRACEABILITY_SCREEN",
            "SEARCH",
            # Experimental features.
            "PROJECT_STATISTICS_SCREEN",
            "REQIF",
            "DIFF",
        ],
        # files_content/ holds an extracted copy of a previous export that
        # reuses the same document UIDs. Leaving it in the document tree fails
        # the build with a duplicate-UID error.
        #
        # review_templates/ is a source of node fragments for
        # tools/seed_review_record.py, not a published document. It is excluded
        # because [GRAMMAR] IMPORT_FROM_FILE resolves relative to the .sdoc
        # file's own directory and rejects any path separator, so a template
        # outside src/ can never reach src/grammar.sgra.
        exclude_doc_paths=[
            "files_content/**",
            "output/**",
            "review_templates/**",
        ],
        server_host="127.0.0.1",
        server_port=5111,
    )
