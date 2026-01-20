#!/usr/bin/env python3

"""CLI entrypoint for protocol downloading.

This script downloads clinical trial protocol PDFs from multiple sources.
The implementation lives in the data-pipeline component.
"""

import sys

from data_pipeline.downloader import main

if __name__ == "__main__":
    sys.exit(main())
