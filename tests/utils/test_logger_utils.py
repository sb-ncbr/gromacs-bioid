import logging

from ...src.utils.logger_utils import (
    close_task_log_output,
    create_task_log_output,
    init_loggers,
)


def test_init_loggers_configures_pipeline_loggers_without_duplicate_handlers():
    init_loggers(verbose=False, very_verbose=False)
    init_loggers(verbose=False, very_verbose=False)

    for logger_name in ("base", "signature", "identifier", "verification"):
        logger = logging.getLogger(logger_name)
        assert len(logger.handlers) == 1


def test_task_log_handler_is_added_and_removed_from_all_pipeline_loggers(tmp_path):
    init_loggers(verbose=False, very_verbose=False)
    log_path = tmp_path / "task.log"

    handler = create_task_log_output(str(log_path))
    for logger_name in ("base", "signature", "identifier", "verification"):
        assert handler in logging.getLogger(logger_name).handlers

    close_task_log_output(handler)
    for logger_name in ("base", "signature", "identifier", "verification"):
        assert handler not in logging.getLogger(logger_name).handlers

    assert handler.stream is None
