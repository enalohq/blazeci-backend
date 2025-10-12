#!/usr/bin/env python3
"""
Monitor GitHub runner ECS tasks
"""
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import json

# Load environment variables
backend_dir = Path(__file__).resolve().parent
load_dotenv(dotenv_path=backend_dir / ".env")

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
ECS_CLUSTER = os.getenv("ECS_CLUSTER", "ECS-ECR-STAGING-API")
ECS_TASK_DEFINITION = os.getenv("ECS_TASK_DEFINITION", "github-runner-task")

def monitor_runner_tasks():
    """Monitor ECS tasks for GitHub runners"""
    print("🔍 GitHub Runner Task Monitor")
    print("=" * 50)
    
    ecs = boto3.client("ecs", region_name=AWS_REGION)
    
    try:
        # Get running tasks
        print("📋 RUNNING TASKS:")
        running_tasks = ecs.list_tasks(
            cluster=ECS_CLUSTER,
            family=ECS_TASK_DEFINITION,
            desiredStatus='RUNNING'
        )
        
        if running_tasks.get('taskArns'):
            # Get detailed task information
            task_details = ecs.describe_tasks(
                cluster=ECS_CLUSTER,
                tasks=running_tasks['taskArns']
            )
            
            for i, task in enumerate(task_details.get('tasks', []), 1):
                task_id = task['taskArn'].split('/')[-1]
                created_at = task.get('createdAt', datetime.now())
                last_status = task.get('lastStatus', 'Unknown')
                
                # Extract trigger information from environment variables
                trigger_info = "Unknown trigger"
                for container in task.get('overrides', {}).get('containerOverrides', []):
                    for env_var in container.get('environment', []):
                        if env_var.get('name') == 'RUNNER_TRIGGER':
                            trigger_info = env_var.get('value', 'Unknown trigger')
                            break
                
                print(f"   {i}. Task: {task_id}")
                print(f"      Status: {last_status}")
                print(f"      Created: {created_at}")
                print(f"      Trigger: {trigger_info}")
                print()
        else:
            print("   ✅ No running tasks")
        
        # Get pending tasks
        print("⏳ PENDING TASKS:")
        pending_tasks = ecs.list_tasks(
            cluster=ECS_CLUSTER,
            family=ECS_TASK_DEFINITION,
            desiredStatus='PENDING'
        )
        
        if pending_tasks.get('taskArns'):
            task_details = ecs.describe_tasks(
                cluster=ECS_CLUSTER,
                tasks=pending_tasks['taskArns']
            )
            
            for i, task in enumerate(task_details.get('tasks', []), 1):
                task_id = task['taskArn'].split('/')[-1]
                created_at = task.get('createdAt', datetime.now())
                last_status = task.get('lastStatus', 'Unknown')
                
                print(f"   {i}. Task: {task_id}")
                print(f"      Status: {last_status}")
                print(f"      Created: {created_at}")
                print()
        else:
            print("   ✅ No pending tasks")
        
        # Get recently stopped tasks (last 10)
        print("🛑 RECENTLY STOPPED TASKS (Last 10):")
        stopped_tasks = ecs.list_tasks(
            cluster=ECS_CLUSTER,
            family=ECS_TASK_DEFINITION,
            desiredStatus='STOPPED'
        )
        
        if stopped_tasks.get('taskArns'):
            # Get up to 10 most recent stopped tasks
            recent_stopped = stopped_tasks['taskArns'][:10]
            task_details = ecs.describe_tasks(
                cluster=ECS_CLUSTER,
                tasks=recent_stopped
            )
            
            for i, task in enumerate(task_details.get('tasks', []), 1):
                task_id = task['taskArn'].split('/')[-1]
                created_at = task.get('createdAt', datetime.now())
                stopped_at = task.get('stoppedAt', 'Unknown')
                stopped_reason = task.get('stoppedReason', 'Unknown')
                
                print(f"   {i}. Task: {task_id}")
                print(f"      Created: {created_at}")
                print(f"      Stopped: {stopped_at}")
                print(f"      Reason: {stopped_reason}")
                print()
        else:
            print("   ✅ No recently stopped tasks")
        
        # Summary
        running_count = len(running_tasks.get('taskArns', []))
        pending_count = len(pending_tasks.get('taskArns', []))
        total_active = running_count + pending_count
        
        print("📊 SUMMARY:")
        print(f"   Running: {running_count}")
        print(f"   Pending: {pending_count}")
        print(f"   Total Active: {total_active}")
        
        if total_active > 1:
            print("   ⚠️  WARNING: Multiple runners detected!")
            print("      This might indicate inefficient resource usage.")
        elif total_active == 1:
            print("   ✅ Optimal: Single runner active")
        else:
            print("   ℹ️  No active runners")
            
    except Exception as e:
        print(f"❌ Error monitoring tasks: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    exit(monitor_runner_tasks())