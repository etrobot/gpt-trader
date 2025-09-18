#!/usr/bin/env python3
"""Run a complete analysis task to test the fixed factor calculation"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import logging
import uuid
from datetime import datetime
from models import Task, TaskStatus
from data_management.analysis_task_runner import run_analysis_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_task():
    """创建一个测试分析任务"""
    task_id = str(uuid.uuid4())
    
    # 创建任务对象
    task = Task(
        id=task_id,
        status=TaskStatus.PENDING,
        progress=0.0,
        message="正在准备分析任务",
        created_at=datetime.now().isoformat(),
        version=1
    )
    
    # 将任务存储在全局字典中（模拟数据库）
    from utils import _tasks_store
    _tasks_store[task_id] = task
    
    return task_id

def run_test_analysis():
    """运行测试分析"""
    print("=== Running Complete Analysis Task ===")
    
    # 创建任务
    task_id = create_test_task()
    print(f"Created task: {task_id}")
    
    try:
        # 运行分析任务，不收集最新数据，只使用数据库中的数据
        run_analysis_task(
            task_id=task_id,
            top_n=10,  # 分析前10个交易对
            selected_factors=None,  # 计算所有因子
            collect_latest_data=False  # 使用数据库现有数据
        )
        
        # 获取任务结果
        from utils import get_task
        task = get_task(task_id)
        
        if task and task.status == TaskStatus.COMPLETED:
            print("✅ Analysis completed successfully!")
            print(f"Message: {task.message}")
            
            if task.result and 'data' in task.result:
                data = task.result['data']
                print(f"Results: {len(data)} symbols analyzed")
                
                # 查找SOMIUSDT的结果
                somi_result = None
                for item in data:
                    if item.get('symbol') == 'SOMIUSDT':
                        somi_result = item
                        break
                
                if somi_result:
                    print(f"\n=== SOMIUSDT Results ===")
                    for key, value in somi_result.items():
                        status = "✅" if value is not None else "❌ None"
                        print(f"  {key}: {value} {status}")
                else:
                    print("ℹ️  SOMIUSDT not found in results (may not be in top 10)")
                    print("Top symbols in results:")
                    for i, item in enumerate(data[:5]):
                        print(f"  {i+1}. {item.get('symbol', 'Unknown')}")
        else:
            print(f"❌ Analysis failed!")
            if task:
                print(f"Status: {task.status}")
                print(f"Message: {task.message}")
                if hasattr(task, 'error'):
                    print(f"Error: {task.error}")
            
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test_analysis()