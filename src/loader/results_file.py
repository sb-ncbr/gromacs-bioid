import json
"""DEPRECATED (frozen 2026-10) — superseded by src_new/loader/. See src/loader/README.md."""
import logging
import os.path
from typing import Any


class ResultsFile:
    """
    A wrapper for JSON file-backed data
    """
    def __init__(self, path: str, log_handler: logging.FileHandler | None = None) -> None:
        self.path: str = path
        self.working_directory: str = os.path.dirname(path)
        self.data: dict[str, Any] = dict()

        self._log_handler: logging.FileHandler | None = log_handler

        self._initialize()

    def is_log_handler_attached(self) -> bool:
        """
        Checks whether logging handler is attached to this results file
        :return: bool
        """
        return self._log_handler is not None

    def get_log_handler(self) -> logging.FileHandler | None:
        """
        :return: logging handler attached to this results file (if present, None otherwise)
        """
        return self._log_handler

    def _initialize(self) -> None:
        """
        Loads the file from disk, if exists, otherwise creates new one
        :return: None
        """
        if os.path.exists(self.path):
            with open(self.path, 'r') as fd:
                data_text: str = fd.read()
                if data_text:
                    self.data = json.loads(data_text)
        else:
            with open(self.path, 'w') as fd:
                ...

    def _save(self) -> None:
        """
        Saves the data to the file
        :return: None
        """
        with open(self.path, 'w') as fd:
            json.dump(self.data, fd, indent=4)

    def get_item(self, path: str, default: Any = None) -> Any:
        """
        Retrieves object from the data
        :param path: URI-like path where slash divides nested dictionaries
        :param default: default value to return
        :raises KeyError: if key is not found and default value is not provided
        :return: value associated with key(s) in the path
        """

        def _default() -> Any:
            if default is None:
                raise KeyError(f"No item found for path: '{path}'")
            return default

        parts: list[str] = path.split('/')
        subpaths, key = parts[:-1], parts[-1]

        current = self.data
        for subpath in subpaths:
            if subpath not in current:
                return _default()
            current = current[subpath]

        if key not in current:
            return _default()

        return current[key]

    def get_item_safe(self, path: str, required_type: Any, default: Any = None) -> Any:
        """
        Same as get_item but enforces correct type
        :param path: URI-like path where slash divides nested dictionaries
        :param required_type: required type of value given the path, used for check in isinstance()
        :param default: default value to return
        :raises KeyError: if key is not found and default value is not provided
        :raises ValueError: if value is of incorrect type
        :return: value associated with key(s) in the path
        """

        value: Any = self.get_item(path, default)
        if not isinstance(value, required_type):
            raise ValueError(f"Incorrect type of item found under path '{path}'."
                             f" Expected {required_type}, got {type(value)}")
        return value

    def item_exists(self, path: str) -> bool:
        """
        Returns whether object given path exists
        :param path: URI-like path where slash divides nested dictionaries
        :return: True if exists
        """
        class Sentinel:
            ...
        return not isinstance(self.get_item(path, default=Sentinel()), Sentinel)

    def set_item(self, path: str, value: Any) -> None:
        """
        Sets object in the data and saves to the underlying file. Creates missing dictionaries if missing
        :param path: URI-like path where slash divides nested dictionaries
        :param value: to be set
        :return: None
        """

        parts: list[str] = path.split('/')
        subpaths, key = parts[:-1], parts[-1]

        current = self.data
        for subpath in subpaths:
            if subpath not in current:
                current[subpath] = dict()
            current = current[subpath]

        current[key] = value
        self._save()


