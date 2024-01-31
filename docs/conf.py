# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
from datetime import datetime, timezone

project = "WordDumb"
copyright = f"{datetime.now(timezone.utc).year}, xxyzz"
author = "xxyzz"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_logo = "../starfish.svg"
html_theme_options = {
    "source_repository": "https://github.com/xxyzz/WordDumb",
    "source_branch": "master",
    "source_directory": "docs/",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/xxyzz/WordDumb",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
        },
        {
            "name": "Liberapay",
            "url": "https://liberapay.com/xxyzz/donate",
            "html": """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80">
              <g transform="matrix(.83012 0 0 .83012-135.4-247.7)">
                <path d="m259.55 385.57c0 5.145-4.169 9.318-9.318 9.318h-77.74c-5.144 0-9.318-4.174-9.318-9.318v-77.74c0-5.145 4.174-9.318 9.318-9.318h77.74c5.149 0 9.318 4.173 9.318 9.318v77.74" fill="#f6c915"/>
                <g fill="#fff">
                  <path d="m202.45 366.03c-3.104 0-5.541-.405-7.311-1.213-1.77-.809-3.039-1.912-3.803-3.313-.766-1.398-1.137-3-1.115-4.818.021-1.814.272-3.748.754-5.803l8.327-34.817 10.164-1.573-9.114 37.768c-.175.786-.273 1.508-.295 2.163-.023.655.098 1.235.36 1.737.262.504.71.908 1.344 1.213.633.307 1.519.504 2.656.591l-1.967 8.06"/>
                  <path d="m239.16 344.33c0 3.19-.525 6.108-1.574 8.753-1.049 2.646-2.503 4.929-4.36 6.852-1.858 1.925-4.087 3.421-6.688 4.491-2.601 1.07-5.432 1.607-8.49 1.607-1.487 0-2.973-.132-4.459-.395l-2.951 11.869h-9.704l10.884-45.37c1.748-.524 3.748-.994 5.999-1.41 2.252-.415 4.689-.622 7.312-.622 2.448 0 4.558.371 6.327 1.114 1.771.743 3.224 1.76 4.361 3.049 1.136 1.29 1.977 2.798 2.523 4.524.546 1.726.82 3.574.82 5.542m-23.802 13.442c.743.175 1.661.262 2.754.262 1.704 0 3.256-.316 4.655-.951 1.398-.633 2.59-1.518 3.574-2.655.982-1.136 1.747-2.501 2.294-4.098.546-1.595.819-3.354.819-5.278 0-1.879-.416-3.475-1.245-4.787-.831-1.311-2.273-1.967-4.327-1.967-1.4 0-2.711.131-3.935.394l-4.589 19.08"/>
                </g>
              </g>
            </svg>
            """,
        },
    ],
}
