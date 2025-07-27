#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
同步记录格式迁移工具

此脚本用于将旧格式的同步时间记录迁移到新格式，添加MD5哈希值。
旧格式: {"file_path": "timestamp"}
新格式: {"file_path": {"timestamp": "timestamp", "md5": "md5_hash"}}

使用方法:
    python migrate_sync_records.py [同步记录文件路径]

如果不提供路径参数，将使用默认路径。
"""

import os
import sys
import json
import hashlib
from datetime import datetime

def calculate_md5(file_path):
    """计算文件的MD5哈希值
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: 文件的MD5哈希值
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def migrate_sync_records(sync_file_path):
    """迁移同步记录格式
    
    Args:
        sync_file_path: 同步记录文件路径
        
    Returns:
        bool: 是否成功迁移
    """
    if not os.path.exists(sync_file_path):
        print(f"错误: 同步记录文件不存在: {sync_file_path}")
        return False
        
    try:
        # 读取同步记录
        with open(sync_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if not content:
            print("同步记录文件为空")
            return False
            
        all_sync_times = json.loads(content)
        if not all_sync_times:
            print("同步记录为空")
            return False
            
        # 记录迁移统计
        total_configs = 0
        total_records = 0
        migrated_records = 0
        failed_records = 0
        
        # 迁移每个配置的记录
        for config_name, sync_times in all_sync_times.items():
            total_configs += 1
            print(f"\n处理配置 '{config_name}':")
            
            # 迁移该配置下的所有记录
            for file_path, sync_info in list(sync_times.items()):
                total_records += 1
                
                # 如果已经是新格式，跳过
                if not isinstance(sync_info, str):
                    print(f"  [已是新格式] {file_path}")
                    continue
                    
                print(f"  迁移: {file_path}")
                
                # 如果文件存在，计算MD5
                if os.path.exists(file_path):
                    try:
                        md5_hash = calculate_md5(file_path)
                        sync_times[file_path] = {
                            'timestamp': sync_info,
                            'md5': md5_hash
                        }
                        migrated_records += 1
                        print(f"    ✓ MD5: {md5_hash}")
                    except Exception as e:
                        print(f"    ✗ 计算MD5失败: {e}")
                        # 使用空MD5
                        sync_times[file_path] = {
                            'timestamp': sync_info,
                            'md5': ''
                        }
                        failed_records += 1
                else:
                    # 如果文件不存在，使用空MD5
                    print(f"    ⚠ 文件不存在，使用空MD5")
                    sync_times[file_path] = {
                        'timestamp': sync_info,
                        'md5': ''
                    }
                    migrated_records += 1
        
        # 保存迁移后的记录
        with open(sync_file_path, 'w', encoding='utf-8') as f:
            json.dump(all_sync_times, f, indent=2, ensure_ascii=False)
            
        # 打印迁移结果
        print("\n迁移完成!")
        print(f"处理配置数: {total_configs}")
        print(f"总记录数: {total_records}")
        print(f"成功迁移: {migrated_records}")
        print(f"迁移失败: {failed_records}")
        print(f"无需迁移: {total_records - migrated_records - failed_records}")
        
        return True
    except Exception as e:
        print(f"迁移过程中出错: {e}")
        return False

def main():
    """主函数"""
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 获取应用数据目录
    app_data_dir = os.path.join(os.getenv('APPDATA') or os.path.expanduser('~/.local/share'), 'FileSyncLog')
    
    # 默认同步记录文件路径
    default_sync_file = os.path.join(script_dir, '_last_sync.json')
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        sync_file_path = sys.argv[1]
    else:
        sync_file_path = default_sync_file
        
    print(f"同步记录迁移工具")
    print(f"迁移文件: {sync_file_path}")
    
    # 执行迁移
    success = migrate_sync_records(sync_file_path)
    
    if success:
        print("\n迁移成功完成！")
    else:
        print("\n迁移过程中出现错误。")
        
if __name__ == "__main__":
    main() 