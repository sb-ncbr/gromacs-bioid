"""
New API endpoint module using src_new modules.

This is a replacement for the deprecated api_endpoint.py which uses old src.* modules.
"""

import os
import sys
from pathlib import Path

from rich import print as rprint

from src_new.pipeline_steps import build_load_and_export_tasks
from src_new.executor.executor import PipelineExecutor
from src_new.results.results_manager import ResultsManager
from src_new.config.loader import RunConfig


def run_analyze(directory: str, task_uuid: str, config_path: str | None = None) -> str | None:
    """
    Runs full BAT analysis (--run) mode using src_new modules.
    
    :param directory: Directory containing input files
    :param task_uuid: Task UUID for tracking
    :param config_path: Optional path to INI config file
    :return: Absolute path to results.json if successful, else None
    """
    from rich import print
    
    print("[cyan][b]-> Entering run mode (src_new)[/b][/cyan]")
    print(f"[b]About to analyse: '{directory}'[/b]")
    
    # Build tasks
    tasks = build_load_and_export_tasks()
    print(f"[green][b]✔ {len(tasks)} task(s) created[/b][/green]")
    
    # Load or create config
    if config_path and os.path.exists(config_path):
        config = RunConfig.from_ini_path(config_path)
        print(f"[cyan]Loaded config from: {config_path}[/cyan]")
    else:
        config = RunConfig.from_default_ini()
        print("[cyan]Using default configuration from config.ini[/cyan]")
    
    # Set the task UUID for PDB deployment file access
    config.pdb.curr_uuid = task_uuid
    
    # Create results manager
    results_path = os.path.join(directory, "results.json")
    results_manager = ResultsManager(results_path)
    
    # Create executor
    executor = PipelineExecutor(
        steps=tasks,
        results_manager=results_manager,
        pipeline_name="BAT3 Load and Export"
    )
    
    print("[cyan][b]-> Launching synchronous executor (will block until finished)[/b][/cyan]")
    executor.run(
        output_directory=directory,
        working_directory=directory,
        run_config=config
    )
    print(f"[green][b]✔ executor has exited[/b][/green]")
    
    print(f"[b]Collecting results from: '{directory}'[/b]")
    if not os.path.exists(results_path):
        print("[red][b]✘ the job failed[/b][/red]")
        return None
    
    return os.path.abspath(results_path)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("[red][b]Usage: python api_endpoint_new.py <directory> <task_uuid> [config_path][/b][/red]")
        sys.exit(1)
    
    directory = sys.argv[1]
    task_uuid = sys.argv[2]
    config_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    result_path = run_analyze(directory, task_uuid, config_path)
    
    if result_path:
        print(f"[green][b]Results written to: {result_path}[/b][/green]")
        sys.exit(0)
    else:
        print("[red][b]Analysis failed[/b][/red]")
        sys.exit(1)
