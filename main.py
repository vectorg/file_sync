from watchdog.observers import Observer
import time
import sys
import os
from datetime import datetime
from file_handler import FileHandler
from sync_utils import should_ignore_file

def main(configs):
    """主函数，处理文件同步和监控
    Args:
        configs: 配置字典
    """
    # 显示当前时间和运行的脚本文件
    script_path = os.path.abspath(sys.argv[0])
    start_message = f"\n=== 文件同步工具 ===\n"
    start_message += f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    start_message += f"运行脚本: {script_path}\n"

    # 创建观察者和处理器列表
    observers = []
    handlers = []
    
    # 为每个配置创建观察者和处理器
    for config_name, config in configs.items():
        # 如果 mode 为 0，跳过此配置
        if config['mode'] == 0:
            continue
            
        # 确保日志目录存在
        log_file = os.path.abspath(config['log_file'])
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        event_handler = FileHandler(config, config_name)
        handlers.append(event_handler)
        
        # 将启动信息写入日志
        config_start_message = start_message + f"日志文件: {log_file}\n"  # 为每个配置添加其对应的日志文件路径
        event_handler._log(config_start_message)
        
        # 预览模式 (mode = 1) 或 预览并更新同步时间模式 (mode = 11)
        if config['mode'] in [1, 11]:
            print(f"\n=== 配置 '{config_name}' 预览 ===")
            event_handler.preview_sync_files()
            
            if config['mode'] == 11:
                print(f"\n正在更新文件同步时间...")
                for root, dirs, files in os.walk(config['source_dir']):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if not should_ignore_file(file_path, config['source_dir'], 
                                               config['ignore_patterns'], 
                                               config['only_sync_files'], 
                                               config['log_file']):
                            event_handler._save_sync_time(file_path)
                print("同步时间更新完成！")
            continue
        
        # 一次性智能同步模式 (mode = 2)
        if config['mode'] == 2:
            print(f"\n=== 配置 '{config_name}' 一次性智能同步 ===")
            event_handler.sync_all_files(check_time=True)
            continue
            
        # 智能同步并监控模式 (mode = 3)
        if config['mode'] == 3:
            print(f"\n=== 配置 '{config_name}' 智能同步并监控 ===")
            event_handler.sync_all_files(check_time=True)
        
        # 完整同步并监控模式 (mode = 4)
        if config['mode'] == 4:
            print(f"\n=== 配置 '{config_name}' 完整同步并监控 ===")
            event_handler.sync_all_files(check_time=False)
        
        # 对 mode 3 和 4 启动文件监控
        if config['mode'] in [3, 4]:
            observer = Observer()
            observer.schedule(event_handler, config['source_dir'], recursive=True)
            observer.start()
            observers.append(observer)
            
            log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 配置 '{config_name}' 监控已启动:\n"
            log_message += f"监控目录: {config['source_dir']}\n"
            # 格式化目标路径显示
            target_paths = []
            for target in config['targets']:
                if isinstance(target, tuple):
                    username, ip, path, _, port = target
                    if port:
                        target_paths.append(f"{username}@{ip}:{path}")
                    else:
                        target_paths.append(f"{username}@{ip}:{path}")
                else:
                    target_paths.append(str(target))
            log_message += f"目标路径: {', '.join(target_paths)}\n"
            log_message += "-" * 60 + "\n"
            event_handler._log(log_message)
    
    # 如果所有配置都是预览模式或者被跳过，直接退出
    if not observers:
        sys.exit(0)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # 停止所有观察者
        for observer in observers:
            observer.stop()
        
        # 记录停止信息
        for handler in handlers:
            if not configs[handler.config_name]['mode'] == 1:  # 只为非预览模式的配置记录停止信息
                log_message = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 监控已停止\n"
                log_message += "-" * 60 + "\n"
                handler._log(log_message)
    
    # 等待所有观察者完成
    for observer in observers:
        observer.join()

if __name__ == "__main__":
    print("请通过config文件运行此程序")
