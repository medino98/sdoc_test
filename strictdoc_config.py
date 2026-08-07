"""
StrictDoc project configuration.

Replaces the deprecated strictdoc.toml format (StrictDoc >= 0.27).
StrictDoc calls create_config() to obtain the project settings.
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
        exclude_doc_paths=[
            "files_content/**",
            "output/**",
        ],
        server_host="127.0.0.1",
        server_port=5111,
    )
