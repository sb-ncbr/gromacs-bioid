import logging
from rich import print

def init_loggers(verbose: bool | None, very_verbose: bool | None) -> None:
    """
    Initializes loggers used by the application
    :param verbose: if True, failure debug logs will be printed
    :param very_verbose: if True, all debug logs will be printed
    :return: None
    """

    verbose_set: bool = verbose if verbose is not None else False
    very_verbose_set: bool = very_verbose if very_verbose is not None else False

    def _add_log_handler(log_name: str,
                         very_verbose_level: int,
                         verbose_level: int,
                         normal_level: int):

        logger = logging.getLogger(log_name)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(process)s/%(thread)d] %(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        if very_verbose_set:
            logger.setLevel(very_verbose_level)
        elif verbose_set:
            logger.setLevel(verbose_level)
        else:
            logger.setLevel(normal_level)

    _add_log_handler(
        "base",  # generic logs about queues, loading, errors, etc.
        very_verbose_level=logging.DEBUG,
        verbose_level=logging.INFO,
        normal_level=logging.INFO,
    )
    _add_log_handler(
        "signature",  # logs considering signature generation
        very_verbose_level=logging.DEBUG,
        verbose_level=logging.WARNING,
        normal_level=logging.FATAL,
    )

    _add_log_handler(
        "identifier",  # logs considering identification of signatures
        very_verbose_level=logging.DEBUG,
        verbose_level=logging.WARNING,
        normal_level=logging.FATAL,
    )

    _add_log_handler(
        "verification",  # logs considering identification of signatures
        very_verbose_level=logging.DEBUG,
        verbose_level=logging.WARNING,
        normal_level=logging.FATAL,
    )

    print(
        f"[b][green]✔  Loggers initialized "
        f"(failures: {verbose_set or very_verbose_set}, "
        f"debug: {very_verbose_set})[/green][/b]"
    )


def create_task_log_output(log_file: str) -> logging.FileHandler:
    """
    Creates temporary handler to capture all logs into file
    :param log_file: path to file to save logs to
    :return: handler (for cleanup later)
    """

    handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    formatter = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)

    logging.getLogger("base").addHandler(handler)
    logging.getLogger("signature").addHandler(handler)
    logging.getLogger("identifier").addHandler(handler)
    logging.getLogger("verification").addHandler(handler)

    return handler

def close_task_log_output(handler: logging.FileHandler) -> None:
    """
    Closes handler associated with logging file
    :param handler: to be closed
    :return: None
    """

    logging.getLogger("base").removeHandler(handler)
    logging.getLogger("signature").removeHandler(handler)
    logging.getLogger("identifier").removeHandler(handler)
    logging.getLogger("verification").removeHandler(handler)
    handler.close()
