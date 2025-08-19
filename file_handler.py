from watchdog.events import FileSystemEventHandler
from datetime import datetime
import os
import time
import json
from sync_utils import sync_to_local, sync_to_remote, should_ignore_file, parse_targets, delete_from_local, delete_from_remote, delete_from_remote_dir, delete_from_local_dir, calculate_md5
from line_ending_handler import print_shell_script_commands

class FileHandler(FileSystemEventHandler):
    def __init__(self, config: dict, config_name: str):
        super().__init__()
        self.source_dir = os.path.abspath(config['source_dir'])
        self.targets = parse_targets(config['targets'])
        self.log_file = os.path.abspath(config['log_file'])
        self.ignore_patterns = config['ignore_patterns']
        self.only_sync_files = config['only_sync_files']
        self.mode = config['mode']
        self.last_sync_file = os.path.abspath(config['last_sync_file'])
        self.config_name = config_name
        self._load_sync_times()

        # 确保本地目标目录存在
        for target in self.targets:
            if not target['remote']:
                os.makedirs(target['path'], exist_ok=True)

        self.last_sync_timestamps = {}
        self.debounce_seconds = 1
        self.last_logged_file = None

    def _load_sync_times(self):
        """加载上次同步时间记录"""
        try:
            if os.path.exists(self.last_sync_file):
                with open(self.last_sync_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                if content:
                    all_sync_times = json.loads(content)
                else:
                    all_sync_times = {}
                self.sync_times = all_sync_times.get(self.config_name, {})
            else:
                self.sync_times = {}
        except Exception as e:
            print(f"加载同步时间记录失败: {e}")
            self.sync_times = {}

    def _save_sync_time(self, file_path):
        """保存文件的同步时间和MD5哈希值"""
        abs_path = os.path.abspath(file_path)
        timestamp = datetime.now().isoformat()
        
        try:
            # 计算文件的MD5哈希值
            md5_hash = calculate_md5(file_path)
            
            all_sync_times = {}
            if os.path.exists(self.last_sync_file):
                with open(self.last_sync_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                if content:
                    all_sync_times = json.loads(content)
                else:
                    all_sync_times = {}
            
            if self.config_name not in all_sync_times:
                all_sync_times[self.config_name] = {}
            
            # 保存时间戳和MD5哈希值
            if abs_path not in all_sync_times[self.config_name]:
                all_sync_times[self.config_name][abs_path] = {}
            
            all_sync_times[self.config_name][abs_path] = {
                'timestamp': timestamp,
                'md5': md5_hash
            }
            
            os.makedirs(os.path.dirname(self.last_sync_file), exist_ok=True)
            with open(self.last_sync_file, 'w', encoding='utf-8') as f:
                json.dump(all_sync_times, f, indent=2, ensure_ascii=False)
            
            self.sync_times = all_sync_times[self.config_name]
        except Exception as e:
            print(f"保存同步时间记录失败: {e}")

    def _need_sync(self, file_path):
        """检查文件是否需要同步
        只有当文件的最后修改时间晚于上次同步时间，并且MD5哈希值不同时，才需要同步。
        """
        abs_path = os.path.abspath(file_path)
        sync_info = self.sync_times.get(abs_path)
        
        if not sync_info:
            return True
        
        try:
            # 处理旧格式（字符串）和新格式（字典）
            if isinstance(sync_info, str):
                # 旧格式：只有时间戳，没有MD5
                last_sync_time_str = sync_info
                last_md5 = None
            else:
                # 新格式：包含时间戳和MD5
                last_sync_time_str = sync_info.get('timestamp')
                last_md5 = sync_info.get('md5')
            
            # 如果没有MD5记录，使用旧的逻辑
            if not last_md5:
                last_sync_time = datetime.fromisoformat(last_sync_time_str)
                last_modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                return last_modified_time > last_sync_time
            
            # 检查修改时间
            last_sync_time = datetime.fromisoformat(last_sync_time_str)
            last_modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            time_changed = last_modified_time > last_sync_time
            
            # 如果时间没有变化，不需要同步
            if not time_changed:
                return False
            
            # 计算当前文件的MD5哈希值
            current_md5 = calculate_md5(file_path)
            
            # 只有当时间变化并且MD5哈希值不同时，才需要同步
            return current_md5 != last_md5
            
        except Exception as e:
            print(f"比较时间或MD5失败: {e}, 文件: {file_path}")
            return True

    def preview_sync_files(self):
        """以树形结构预览将要同步的文件"""
        print("\n目标目录:")
        for target in self.targets:
            if target['remote']:
                print(f"→ 远程目标: {target['server']}:{target['path']}")
            else:
                print(f"→ 本地目标: {target['path']}")
        
        print(f"\n将从 {self.source_dir} 同步的文件:")
        
        file_tree = {}
        for root, dirs, files in os.walk(self.source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if should_ignore_file(file_path, self.source_dir, self.ignore_patterns, 
                                    self.only_sync_files, self.log_file):
                    continue
                relative_path = os.path.relpath(file_path, self.source_dir)
                
                parts = relative_path.split(os.sep)
                current = file_tree
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = None
        
        def print_tree(node, prefix="", is_last=True):
            items = list(node.items())
            for i, (name, subtree) in enumerate(items):
                is_current_last = i == len(items) - 1
                print(f"{prefix}{'└── ' if is_current_last else '├── '}{name}")
                if subtree is not None:
                    new_prefix = prefix + ("    " if is_current_last else "│   ")
                    print_tree(subtree, new_prefix)
        
        print_tree(file_tree)

    def _log(self, message, write_to_file=True, write_to_console=True):
        """统一的日志记录方法
        Args:
            message: 日志消息
            write_to_file: 是否写入文件
            write_to_console: 是否输出到控制台
        """
        if write_to_file:
            with open(self.log_file, "a", encoding='utf-8') as log_file:
                log_file.write(message)
        if write_to_console:
            print(message, end='')

    def _sync_file(self, src_path):
        """同步单个文件到所有目标"""
        if should_ignore_file(src_path, self.source_dir, self.ignore_patterns, 
                            self.only_sync_files, self.log_file):
            return False

        # 添加检查是否需要同步
        if not self._need_sync(src_path):
            sync_info = self.sync_times.get(src_path, {})
            
            try:
                # 处理旧格式（字符串）和新格式（字典）
                if isinstance(sync_info, str):
                    last_sync_time_str = sync_info
                    last_md5 = "未记录"
                else:
                    last_sync_time_str = sync_info.get('timestamp', '')
                    last_md5 = sync_info.get('md5', '未记录')
                
                last_sync_time = datetime.fromisoformat(last_sync_time_str) if last_sync_time_str else datetime.min
                last_modified_time = datetime.fromtimestamp(os.path.getmtime(src_path))
                current_md5 = calculate_md5(src_path)
                
                log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 文件无需同步: {src_path}\n"
                log_message += f"_sync_file: 上次同步时间: {last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                log_message += f"_sync_file: 文件修改时间: {last_modified_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                log_message += f"_sync_file: 时间是否变化: {'是' if last_modified_time > last_sync_time else '否'}\n"
                log_message += f"_sync_file: 文件MD5: {current_md5}\n"
                log_message += f"_sync_file: 上次MD5: {last_md5}\n"
                log_message += f"_sync_file: MD5是否变化: {'是' if current_md5 != last_md5 else '否'}\n"
                log_message += f"_sync_file: 同步条件: 时间变化 且 MD5变化\n"
                self._log(log_message)
            except Exception as e:
                print(f"获取同步信息失败: {e}, 文件: {src_path}")
            return False

        relative_path = os.path.relpath(src_path, self.source_dir)
        current_time = time.time()

        # 检查是否需要同步（防抖）
        if (relative_path in self.last_sync_timestamps and 
            current_time - self.last_sync_timestamps[relative_path] < self.debounce_seconds):
            return False

        self.last_sync_timestamps[relative_path] = current_time

        # 记录日志
        if relative_path != self.last_logged_file:
            log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            log_message += f"同步文件: {relative_path}\n"
            self._log(log_message)
            self.last_logged_file = relative_path

        # 同步到所有目标
        for target in self.targets:
            if target['remote']:
                remote_path = os.path.join(target['path'], relative_path).replace('\\', '/')
                sync_to_remote(src_path, remote_path, target)
            else:
                dest_path = os.path.join(target['path'], relative_path)
                sync_to_local(src_path, dest_path)

        # 同步完成后保存同步时间
        self._save_sync_time(src_path)
        
        # 检查是否需要打印特殊命令
        print_shell_script_commands(src_path, self.source_dir)
        
        return True

    def sync_all_files(self, check_time=False):
        """初始化时同步所有文件"""
        log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始初始同步...\n"
        log_message += "-" * 60 + "\n"
        self._log(log_message)

        synced_count = 0
        for root, dirs, files in os.walk(self.source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if should_ignore_file(file_path, self.source_dir, self.ignore_patterns, 
                                    self.only_sync_files, self.log_file):
                    continue
                
                # 添加时间检查
                if check_time and not self._need_sync(file_path):
                    continue
                
                if self._sync_file(file_path):
                    synced_count += 1

        log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        log_message += f"初始同步完成！已同步 {synced_count} 个文件。\n"
        log_message += "-" * 60 + "\n"
        self._log(log_message)

    def on_modified(self, event):
        """文件修改事件处理"""
        if event.is_directory:
            return
        
        file_path = event.src_path

        if should_ignore_file(file_path, self.source_dir, self.ignore_patterns, 
                         self.only_sync_files, self.log_file):
            return
        
        # 检查是否在防抖时间内
        current_time = time.time()
        last_time = self.last_sync_timestamps.get(file_path, 0)
        if current_time - last_time < self.debounce_seconds:
            # 防抖：忽略文件变更
            log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 防抖：忽略文件变更"
            log_message += f": {file_path}\n" if self.last_logged_file != file_path else ", "
            log_message += f"距上次触发: {current_time - last_time:.3f}秒\n"
            self._log(log_message, write_to_console=False)
            return
        
        # 更新最后同步时间戳
        self.last_sync_timestamps[file_path] = current_time
        
        # 检查是否需要同步
        if not self._need_sync(file_path):
            sync_info = self.sync_times.get(file_path, {})
            
            try:
                # 处理旧格式（字符串）和新格式（字典）
                if isinstance(sync_info, str):
                    last_sync_time_str = sync_info
                    last_md5 = "未记录"
                else:
                    last_sync_time_str = sync_info.get('timestamp', '')
                    last_md5 = sync_info.get('md5', '未记录')
                
                last_sync_time = datetime.fromisoformat(last_sync_time_str) if last_sync_time_str else datetime.min
                last_modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                current_md5 = calculate_md5(file_path)
                
                log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 检测到文件变更但无需同步: {file_path}\n"
                log_message += f"上次同步时间: {last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                log_message += f"文件修改时间: {last_modified_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                log_message += f"时间是否变化: {'是' if last_modified_time > last_sync_time else '否'}\n"
                log_message += f"文件MD5: {current_md5}\n"
                log_message += f"上次MD5: {last_md5}\n"
                log_message += f"MD5是否变化: {'是' if current_md5 != last_md5 else '否'}\n"
                log_message += f"同步条件: 时间变化 且 MD5变化\n"
                self._log(log_message, write_to_console=False)
            except Exception as e:
                print(f"获取同步信息失败: {e}, 文件: {file_path}")
                
            self.last_logged_file = file_path
            return
        
        self._sync_file(file_path)
        self.last_logged_file = file_path

    def on_deleted(self, event):
        """文件删除事件处理"""
        file_path = event.src_path

        if should_ignore_file(file_path, self.source_dir, self.ignore_patterns, 
                         self.only_sync_files, self.log_file):
            return
        
        # 记录日志
        log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        if event.is_directory:
            log_message += f"检测到目录删除: {os.path.relpath(file_path, self.source_dir)}\n"
        else:
            log_message += f"检测到文件删除: {os.path.relpath(file_path, self.source_dir)}\n"
        self._log(log_message)
        
        # 删除所有目标中的对应文件或目录
        self._delete_file(file_path, event.is_directory)
        
        # 从同步时间记录中删除该文件
        if not event.is_directory:
            self._remove_sync_time(file_path)

    def _delete_file(self, src_path, is_directory=False):
        """删除所有目标中的对应文件或目录"""
        relative_path = os.path.relpath(src_path, self.source_dir)
        
        # 删除所有目标中的对应文件或目录
        for target in self.targets:
            try:
                if target['remote']:
                    remote_path = os.path.join(target['path'], relative_path).replace('\\', '/')
                    if is_directory:
                        delete_from_remote_dir(remote_path, target)
                        log_message = f"已删除远程目录: {target['server']}:{remote_path}\n"
                    else:
                        delete_from_remote(remote_path, target)
                        log_message = f"已删除远程文件: {target['server']}:{remote_path}\n"
                else:
                    dest_path = os.path.join(target['path'], relative_path)
                    if is_directory:
                        delete_from_local_dir(dest_path)
                        log_message = f"已删除本地目录: {dest_path}\n"
                    else:
                        delete_from_local(dest_path)
                        log_message = f"已删除本地文件: {dest_path}\n"
                
                self._log(log_message, write_to_console=False)
            except Exception as e:
                error_message = f"删除{'目录' if is_directory else '文件'}失败: {e}\n"
                self._log(error_message)

    def _remove_sync_time(self, file_path):
        """从同步时间记录中删除文件"""
        abs_path = os.path.abspath(file_path)
        
        try:
            all_sync_times = {}
            if os.path.exists(self.last_sync_file):
                with open(self.last_sync_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                if content:
                    all_sync_times = json.loads(content)
                else:
                    all_sync_times = {}
            
            if self.config_name in all_sync_times and abs_path in all_sync_times[self.config_name]:
                del all_sync_times[self.config_name][abs_path]
                
                os.makedirs(os.path.dirname(self.last_sync_file), exist_ok=True)
                with open(self.last_sync_file, 'w', encoding='utf-8') as f:
                    json.dump(all_sync_times, f, indent=2, ensure_ascii=False)
                
                self.sync_times = all_sync_times[self.config_name]
        except Exception as e:
            print(f"删除同步时间记录失败: {e}")
