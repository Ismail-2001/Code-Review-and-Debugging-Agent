import os
import time
from graph import app
from utils.config import load_config
from state import CodeReviewState

def main():
    """Main entry point for running the code review."""
    print("🚀 CodeGuardian Analysis Starting...")
    
    # Example input
    local_path = "."
    config = load_config(local_path)
    
    initial_state = {
        "repository_url": "local",
        "local_path": local_path,
        "review_scope": "full",
        "config": config,
        "auto_fix_enabled": config.get("auto_fix", {}).get("enabled", False),
        "messages": [],
        "errors": [],
        "static_analysis_findings": [],
        "pattern_analysis_findings": [],
        "security_findings": [],
        "performance_findings": [],
        "testing_findings": [],
        "logic_findings": [],
        "files_analyzed": 0,
        "total_files": 0,
        "analysis_start_time": time.time()
    }
    
    # Run the workflow
    thread_config = {"configurable": {"thread_id": "review-run-001"}}
    
    try:
        results = app.invoke(initial_state, thread_config)
        print("\n✅ Analysis Complete!")
        print(f"Findings Synthesized: {len(results.get('all_findings', []))}")
        print(f"Report Generated: {results.get('current_step')}")
        
    except Exception as e:
        print(f"❌ Analysis Failed: {str(e)}")

if __name__ == "__main__":
    main()
