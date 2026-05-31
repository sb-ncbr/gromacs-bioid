"""Parallel execution utilities for BAT3 pipeline."""

from __future__ import annotations

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Callable, TypeVar, Any

T = TypeVar('T')
R = TypeVar('R')


def run_with_process_pool(
    max_workers: int,
    func: Callable[[T], R],
    items: list[T],
) -> list[R]:
    """Run a function over items using a process pool.
    
    Args:
        max_workers: Maximum number of worker processes.
        func: Function to apply to each item.
        items: List of items to process.
        
    Returns:
        List of results in the same order as items.
    """
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as executor:
        return list(executor.map(func, items))


def run_with_thread_pool(
    max_workers: int,
    func: Callable[[T], R],
    items: list[T],
) -> list[R]:
    """Run a function over items using a thread pool.
    
    Args:
        max_workers: Maximum number of worker threads.
        func: Function to apply to each item.
        items: List of items to process.
        
    Returns:
        List of results in the same order as items.
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(func, items))
