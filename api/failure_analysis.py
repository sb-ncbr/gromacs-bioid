"""
Failure Analysis API - Analyzes ALL failed BAT3 validation runs.

Provides comprehensive overview of where validation pipeline is failing.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# Add bat3 to path for DB access
sys.path.insert(0, '/home/tomsko/work/bat3')

OUTPUT_DIR = Path("/data/validation")


class FailureAnalyzer:
    """Analyzes failure patterns across ALL BAT3 validation runs."""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.results_cache = {}
    
    def get_all_runs(self, limit: int = 1000) -> List[Path]:
        """Get all run directories."""
        if not self.output_dir.exists():
            return []
        return sorted([
            d for d in self.output_dir.iterdir() 
            if d.is_dir() and d.name.isdigit()
        ], key=lambda x: int(x.name), reverse=True)[:limit]
    
    def get_db_failed_runs(self, limit: int = None) -> List[Dict]:
        """Get ALL failed runs from database (no limit by default)."""
        try:
            from validation.src.db import get_session, Bat3Run, MddbEntry
            
            session = get_session()
            
            query = session.query(Bat3Run, MddbEntry).join(
                MddbEntry, Bat3Run.entry_id == MddbEntry.id
            ).filter(
                Bat3Run.status == 'failed'
            ).order_by(Bat3Run.started_at.desc())
            
            # No limit if not specified - get ALL failed runs
            if limit:
                query = query.limit(limit)
            
            failed_runs = query.all()
            
            return [
                {
                    "run_id": str(run.id),
                    "entry_id": str(run.entry_id),
                    "entry_accession": entry.project_local_accession if entry else "unknown",
                    "started_at": str(run.started_at),
                    "error_message": run.error_message,
                    "has_results_json": (self.output_dir / str(run.id) / "results.json").exists()
                }
                for run, entry in failed_runs
            ]
        except Exception as e:
            logger.error(f"Failed to query database: {e}")
            return []
    
    def get_results_json(self, run_dir: Path) -> Optional[Dict]:
        """Load results.json from a run directory."""
        results_path = run_dir / "results.json"
        if not results_path.exists():
            return None
        
        try:
            with open(results_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load {results_path}: {e}")
            return None
    
    def analyze_run(self, run_id: str, results: Dict) -> Dict[str, Any]:
        """Analyze a single run's results."""
        analysis = {
            "run_id": run_id,
            "has_results": True,
            "pipeline_status": results.get("pipeline", {}).get("status", "unknown"),
            "created_at": results.get("created_at"),
            "updated_at": results.get("updated_at"),
            "tasks": {},
            "failed_tasks": [],
            "warning_tasks": [],
            "skipped_tasks": [],
            "critical_errors": results.get("critical_errors", []),
            "warnings": results.get("warnings", []),
            "failure_point": None,
            "duration_seconds": None
        }
        
        # Calculate duration
        if results.get("pipeline", {}).get("started_at") and results.get("pipeline", {}).get("finished_at"):
            try:
                start = datetime.fromisoformat(results["pipeline"]["started_at"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(results["pipeline"]["finished_at"].replace("Z", "+00:00"))
                analysis["duration_seconds"] = (end - start).total_seconds()
            except:
                pass
        
        # Analyze each task
        tasks = results.get("tasks", {})
        
        for task_id, task_data in tasks.items():
            status = task_data.get("status", "unknown")
            
            task_info = {
                "status": status,
                "name": task_data.get("name", task_id),
                "started_at": task_data.get("started_at"),
                "finished_at": task_data.get("finished_at"),
                "duration_seconds": None,
                "error": None
            }
            
            # Calculate task duration
            if task_data.get("started_at") and task_data.get("finished_at"):
                try:
                    start = datetime.fromisoformat(task_data["started_at"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(task_data["finished_at"].replace("Z", "+00:00"))
                    task_info["duration_seconds"] = (end - start).total_seconds()
                except:
                    pass
            
            analysis["tasks"][task_id] = task_info
            
            if status == "failed":
                analysis["failed_tasks"].append(task_id)
                # Get error from critical_errors
                for error in analysis["critical_errors"]:
                    if error.get("task_id") == task_id:
                        task_info["error"] = error
                        break
            elif status == "warning":
                analysis["warning_tasks"].append(task_id)
            elif status == "skipped":
                analysis["skipped_tasks"].append(task_id)
        
        # Determine failure point
        if analysis["failed_tasks"]:
            task_order = list(tasks.keys())
            for task_id in task_order:
                if task_id in analysis["failed_tasks"]:
                    analysis["failure_point"] = {
                        "task_id": task_id,
                        "task_name": analysis["tasks"][task_id]["name"],
                        "error": analysis["tasks"][task_id].get("error")
                    }
                    break
        
        return analysis
    
    def analyze_all_failures(self, file_limit: int = 500) -> Dict[str, Any]:
        """Comprehensive failure analysis from ALL database failures + results files."""
        
        # Get ALL failed runs from database (no limit)
        print("Fetching ALL failed runs from database...", file=sys.stderr)
        db_failed = self.get_db_failed_runs()  # NO LIMIT
        print(f"Found {len(db_failed)} failed runs in database", file=sys.stderr)
        
        # Analyze runs with results.json (limited for performance)
        print(f"Analyzing up to {file_limit} results.json files...", file=sys.stderr)
        runs = self.get_all_runs(limit=file_limit)
        analyses_with_results = []
        task_failures = defaultdict(int)
        task_warnings = defaultdict(int)
        error_codes = defaultdict(int)
        failure_points = defaultdict(int)
        
        for run_dir in runs:
            run_id = run_dir.name
            results = self.get_results_json(run_dir)
            
            if results is None:
                continue
            
            analysis = self.analyze_run(run_id, results)
            analyses_with_results.append(analysis)
            
            # Aggregate statistics
            if analysis["pipeline_status"] == "failed" or analysis["failed_tasks"]:
                for task_id in analysis["failed_tasks"]:
                    task_failures[task_id] += 1
                
                if analysis["failure_point"]:
                    failure_points[analysis["failure_point"]["task_id"]] += 1
                
                for error in analysis["critical_errors"]:
                    code = error.get("code", "unknown")
                    error_codes[code] += 1
            
            for task_id in analysis["warning_tasks"]:
                task_warnings[task_id] += 1
        
        # Categorize ALL database failures
        failures_with_results = [f for f in db_failed if f["has_results_json"]]
        failures_without_results = [f for f in db_failed if not f["has_results_json"]]
        
        # Categorize errors from ALL database failures
        error_categories = defaultdict(int)
        for failure in db_failed:
            error_msg = failure.get("error_message", "") or ""
            if "local_accession" in error_msg:
                error_categories["Code bug (local_accession)"] += 1
            elif "Connection aborted" in error_msg or "timeout" in error_msg.lower():
                error_categories["Network/Timeout"] += 1
            elif "Cancelled" in error_msg:
                error_categories["Cancelled/Interrupted"] += 1
            elif "download" in error_msg.lower():
                error_categories["Download Failure"] += 1
            elif "results.json not found" in error_msg.lower() or not failure.get("has_results_json"):
                error_categories["Hung before completion"] += 1
            else:
                error_categories["Other"] += 1
        
        # Sort
        task_failures_sorted = sorted(task_failures.items(), key=lambda x: x[1], reverse=True)
        task_warnings_sorted = sorted(task_warnings.items(), key=lambda x: x[1], reverse=True)
        error_codes_sorted = sorted(error_codes.items(), key=lambda x: x[1], reverse=True)
        failure_points_sorted = sorted(failure_points.items(), key=lambda x: x[1], reverse=True)
        error_categories_sorted = sorted(error_categories.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "analyzed_at": datetime.now().isoformat(),
            "database": {
                "total_failed_runs": len(db_failed),
                "with_results_json": len(failures_with_results),
                "without_results_json": len(failures_without_results),
                "error_categories": dict(error_categories_sorted),
                "recent_failures": db_failed[:50]  # Show most recent 50
            },
            "results_files": {
                "runs_analyzed": len(analyses_with_results),
                "task_failures": dict(task_failures_sorted),
                "task_warnings": dict(task_warnings_sorted),
                "error_codes": dict(error_codes_sorted),
                "failure_points": dict(failure_points_sorted),
            },
            "summary": {
                "total_db_failures": len(db_failed),
                "hung_before_completion": len(failures_without_results),
                "completed_with_errors": len(failures_with_results),
                "most_common_error_category": error_categories_sorted[0] if error_categories_sorted else None,
                "most_failing_task": task_failures_sorted[0] if task_failures_sorted else None,
                "primary_failure_point": failure_points_sorted[0] if failure_points_sorted else None,
            },
            "recommendations": self._generate_recommendations(
                error_categories_sorted,
                failure_points_sorted,
                len(failures_without_results)
            )
        }
    
    def _generate_recommendations(self, error_categories, failure_points, hung_count) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        if hung_count > 0:
            recommendations.append(
                f"🔴 CRITICAL: {hung_count} runs hung before writing results.json. "
                "BAT3 executor is likely hanging during analysis. Check for infinite loops or deadlocks."
            )
        
        for category, count in error_categories[:3]:
            if "Network" in category or "Timeout" in category:
                recommendations.append(
                    f"🟡 Network issues: {count} failures due to timeouts/connection errors. "
                    "Consider increasing timeouts or implementing retry logic."
                )
            elif "Code bug" in category:
                recommendations.append(
                    f"🔧 Code bug: {count} failures due to known bug. Should be fixed."
                )
            elif "Download" in category:
                recommendations.append(
                    f"📥 Download failures: {count} failures downloading files. "
                    "mdfind fallback should help with this."
                )
            elif "Hung" in category:
                pass  # Already covered in CRITICAL
        
        if failure_points:
            task_id, count = failure_points[0]
            recommendations.append(
                f"⚠️  Most common failure point: {task_id} ({count} runs). "
                "Investigate this task's implementation."
            )
        
        return recommendations


def analyze_failures_api(file_limit: int = 500) -> Dict[str, Any]:
    """
    API endpoint: Comprehensive failure analysis of ALL failed runs.
    
    Args:
        file_limit: Max result files to analyze (database has NO limit)
    
    Returns:
        Comprehensive failure analysis report
    """
    analyzer = FailureAnalyzer()
    return analyzer.analyze_all_failures(file_limit=file_limit)


if __name__ == "__main__":
    print("Running comprehensive failure analysis of ALL failed runs...", file=sys.stderr)
    results = analyze_failures_api()
    
    print(f"\n{'='*80}", file=sys.stderr)
    print("FAILURE ANALYSIS SUMMARY - ALL RUNS", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    
    print(f"\nDatabase Failures: {results['database']['total_failed_runs']:,}", file=sys.stderr)
    print(f"  - With results.json: {results['database']['with_results_json']:,}", file=sys.stderr)
    print(f"  - Without results.json (HUNG): {results['database']['without_results_json']:,}", file=sys.stderr)
    
    print(f"\nError Categories:", file=sys.stderr)
    for category, count in results['database']['error_categories'].items():
        print(f"  {category}: {count:,}", file=sys.stderr)
    
    print(f"\nTask Failures (from results.json):", file=sys.stderr)
    for task, count in list(results['results_files']['task_failures'].items())[:5]:
        print(f"  {task}: {count}", file=sys.stderr)
    
    print(f"\nFailure Points:", file=sys.stderr)
    for task, count in list(results['results_files']['failure_points'].items())[:5]:
        print(f"  {task}: {count}", file=sys.stderr)
    
    print(f"\nRecommendations:", file=sys.stderr)
    for rec in results['recommendations'][:5]:
        print(f"  {rec}", file=sys.stderr)
    
    print(f"\n{'='*80}", file=sys.stderr)
