#!/usr/bin/env python3
"""
Check ECS service desired count
"""
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
backend_dir = Path(__file__).resolve().parent
load_dotenv(dotenv_path=backend_dir / ".env")

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
ECS_CLUSTER = os.getenv("ECS_CLUSTER", "ECS-ECR-STAGING-API")
ECS_SERVICE_NAME = os.getenv("ECS_SERVICE_NAME", "github-runner-task-service-7ub1dmt0")

def check_ecs_service():
    """Check ECS service configuration"""
    print("🔍 ECS Service Configuration Check")
    print("=" * 40)
    print(f"Cluster: {ECS_CLUSTER}")
    print(f"Service: {ECS_SERVICE_NAME}")
    print(f"Region: {AWS_REGION}")
    print()
    
    ecs = boto3.client("ecs", region_name=AWS_REGION)
    
    try:
        # List all services first to see what exists
        print("📋 LISTING ALL SERVICES IN CLUSTER:")
        services_response = ecs.list_services(cluster=ECS_CLUSTER)
        
        if services_response.get('serviceArns'):
            for i, service_arn in enumerate(services_response['serviceArns'], 1):
                service_name = service_arn.split('/')[-1]
                print(f"   {i}. {service_name}")
        else:
            print("   ❌ No services found in cluster")
            return 1
        
        print()
        
        # Check if our specific service exists
        print(f"🔍 CHECKING SERVICE: {ECS_SERVICE_NAME}")
        try:
            service_response = ecs.describe_services(
                cluster=ECS_CLUSTER,
                services=[ECS_SERVICE_NAME]
            )
            
            services = service_response.get('services', [])
            failures = service_response.get('failures', [])
            
            if failures:
                print("❌ SERVICE NOT FOUND:")
                for failure in failures:
                    print(f"   Reason: {failure.get('reason', 'Unknown')}")
                    print(f"   ARN: {failure.get('arn', 'Unknown')}")
                return 1
                
            if not services:
                print("❌ Service not found in cluster")
                return 1
                
            service = services[0]
            
            print("✅ SERVICE FOUND:")
            print(f"   Service Name: {service.get('serviceName', 'Unknown')}")
            print(f"   Status: {service.get('status', 'Unknown')}")
            print(f"   Desired Count: {service.get('desiredCount', 0)}")
            print(f"   Running Count: {service.get('runningCount', 0)}")
            print(f"   Pending Count: {service.get('pendingCount', 0)}")
            print(f"   Task Definition: {service.get('taskDefinition', 'Unknown')}")
            print()
            
            # Check deployment status
            deployments = service.get('deployments', [])
            if deployments:
                print("📦 DEPLOYMENTS:")
                for i, deployment in enumerate(deployments, 1):
                    print(f"   {i}. Status: {deployment.get('status', 'Unknown')}")
                    print(f"      Desired: {deployment.get('desiredCount', 0)}")
                    print(f"      Running: {deployment.get('runningCount', 0)}")
                    print(f"      Pending: {deployment.get('pendingCount', 0)}")
            
            # Summary
            desired = service.get('desiredCount', 0)
            running = service.get('runningCount', 0)
            
            print("📊 SUMMARY:")
            if desired == 0:
                print("   ⚠️  Service has desired count of 0 (no runners will be maintained)")
            elif desired == running:
                print(f"   ✅ Service is healthy (desired: {desired}, running: {running})")
            else:
                print(f"   ⚠️  Service is not at desired state (desired: {desired}, running: {running})")
                
            return 0
            
        except Exception as e:
            print(f"❌ Error checking service: {e}")
            return 1
            
    except Exception as e:
        print(f"❌ Error connecting to ECS: {e}")
        return 1

if __name__ == "__main__":
    exit(check_ecs_service())