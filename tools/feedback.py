#!/usr/bin/env python3
"""Repository entry point for the installed viral-learn feedback CLI."""

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "viral-learn"
    / "scripts"
    / "feedback.py"
)
SPEC = importlib.util.spec_from_file_location("viral_learn_feedback", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError("Unable to load feedback CLI from {}".format(MODULE_PATH))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

# Preserve the import surface used by repository tests and local callers.
FeedbackError = MODULE.FeedbackError
append_event = MODULE.append_event
compare_metric_events = MODULE.compare_metric_events
list_lessons = MODULE.list_lessons
load_events = MODULE.load_events
make_editorial_event = MODULE.make_editorial_event
make_lesson_event = MODULE.make_lesson_event
make_lesson_status_event = MODULE.make_lesson_status_event
make_metric_event = MODULE.make_metric_event
metric_calculation = MODULE.metric_calculation
validate_event = MODULE.validate_event
main = MODULE.main


if __name__ == "__main__":
    sys.exit(main())
