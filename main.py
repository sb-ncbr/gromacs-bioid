import argparse
from rich import print

parser = argparse.ArgumentParser(
                    prog='BAT v2',
                    description='Biomolecule Analysis Toolkit (BAT) for molecular dynamics simulations',
                    epilog='(c) Tomas Pavlik, 2025',
                    formatter_class=argparse.RawTextHelpFormatter
)

# standard mode
parser.add_argument('-r', '--run', action='store_true',
                    help="execute the workflow (once)")
parser.add_argument('-i', '--input', help="directory containing simulations (folders)")
parser.add_argument('-t','--task', action='append', help='task to execute')

# stats mode
parser.add_argument('-s','--stats', action='append', help='stats to aggregate')


# misc arguments
parser.add_argument('-v', '--verbose', action='store_true',
                    help="emit non-critical failure messages (default: False)")
parser.add_argument('-vv', '--very_verbose', action='store_true',
                    help="emit all debug messages (default: False)")

args = parser.parse_args()

from src.utils.logger_utils import init_loggers
from src.utils.string_utils import print_motd
from src.utils.file_utils import list_folders_in_directory
from src.utils.sync_databases import sync

print_motd()
init_loggers(args.verbose, args.very_verbose)

sync()

if args.run:
    from src.executor.task_creator import TaskType, parse_task_types, create_tasks_for_simulations
    from src.executor.task import Task
    from src.executor.core import ExecutorCore

    print("[cyan][b]-> Entering run mode[/b][/cyan]")

    if args.input is None:
        print("[red][b]✘  --input directory was not provided[/b][/red]")
        exit(1)
    sim_dirs: list[str] = list_folders_in_directory(args.input)

    tasks_to_exec: set[TaskType] = parse_task_types(args.task, verbose=True)
    if not tasks_to_exec:
        print("[red][b]✘  no tasks to be executed, exiting![/b][/red]")
        exit(1)

    tasks: list[Task] = create_tasks_for_simulations(sim_dirs, tasks_to_exec)
    if not tasks:
        print("[red][b]✘  no tasks to be executed, exiting![/b][/red]")
        exit(1)

    executor: ExecutorCore = ExecutorCore(terminate_on_finished=True, block_until_finished=True)
    for task in tasks:
        executor.add_task(task)

    print("[cyan][b]-> Launching async executor[/b][/cyan]")
    executor.run()

    #executor.shutdown()

elif args.stats is not None:
    from src.stats.stats_aggregator import StatsAggregatorManager

    print("[cyan][b]-> Entering stats mode[/b][/cyan]")

    if args.input is None:
        print("[red][b]✘  --input directory was not provided[/b][/red]")
        exit(1)
    sim_dirs: list[str] = list_folders_in_directory(args.input)

    stats_manager: StatsAggregatorManager = StatsAggregatorManager(sim_dirs)
    stats_manager.run_aggregators(args.stats, verbose=True)

else:
    print("[red][b]✘ no mode selected[/b][/red]")
