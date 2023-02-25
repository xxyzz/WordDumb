# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "WordDumb"
copyright = "2023, xxyzz"
author = "xxyzz"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
html_logo = "../starfish.svg"
html_theme_options = {
    "source_repository": "https://github.com/xxyzz/WordDumb/",
    "source_branch": "master",
    "source_directory": "docs/",
    "announcement": "Testing features: Word Wise for non-English Kindle books, use POS type, improve Word Wise table loading speed, more Word Wise gloss languages.",
}