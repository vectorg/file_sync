import os
import subprocess
from datetime import datetime
import json
from fnmatch import fnmatch
import paramiko

def parse_targets(targets):
    """解析目标路径列表，区分本地和远程路径
    
    Args:
        targets: 目标路径列表，远程路径格式为 (用户名, IP, 路径, 密码, 端口) 元组
        
    Returns:
        解析后的目标配置列表
    """
    parsed_targets = []
    for target in targets:
        if isinstance(target, tuple):  # 远程路径
            username, server_ip, remote_path, password, port = target
            parsed_targets.append({
                'remote': True,
                'server': f"{username}@{server_ip}",
                'path': remote_path,
                'password': password,
                'port': port or 22  # 如果端口为 None，使用默认端口 22
            })
        else:  # 本地路径
            parsed_targets.append({
                'remote': False,
                'path': os.path.abspath(target)
            })
    return parsed_targets

def sync_to_local(source_path, destination_path):
    """同步到本地目标目录
    
    Args:
        source_path: 源文件路径
        destination_path: 目标文件路径
    """
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    try:
        import shutil
        shutil.copy2(source_path, destination_path)
    except Exception as e:
        raise

def sync_to_remote(source_path, remote_path, target):
    """同步到远程服务器，有密码时使用paramiko，无密码时使用scp"""
    try:
        server = target['server'].split('@')[1]
        if '#' in server:  # 如果服务器地址中包含端口，需要去掉
            server = server.split('#')[0]
        
        # 如果提供了密码，使用paramiko
        if target.get('password'):
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(
                    server,
                    port=target['port'],
                    username=target['server'].split('@')[0],
                    password=target['password']
                )
                
                sftp = ssh.open_sftp()
                remote_dir = os.path.dirname(remote_path)
                ssh.exec_command(f"mkdir -p '{remote_dir}'")
                sftp.put(source_path, remote_path)
            finally:
                ssh.close()
        
        # 如果没有提供密码，使用scp（依赖SSH密钥），不指定端口
        else:
            # 创建远程目录
            remote_dir = os.path.dirname(remote_path)
            mkdir_cmd = f"ssh {target['server']} \"mkdir -p '{remote_dir}'\""
            subprocess.run(mkdir_cmd, shell=True, check=True)
            
            # 执行scp命令
            scp_cmd = f"scp \"{source_path}\" \"{target['server']}:{remote_path}\""
            subprocess.run(scp_cmd, shell=True, check=True)
            
    except (subprocess.CalledProcessError, paramiko.SSHException) as e:
        print(f"远程同步失败: {e}")
        raise

def should_ignore_file(file_path, source_dir, ignore_patterns, only_sync_files, log_file):
    """检查文件是否应该被忽略
    根据配置文件中的 ignore_patterns 和 only_sync_files 进行判断
    
    Args:
        file_path: 文件路径
        source_dir: 源目录
        ignore_patterns: 忽略模式列表
        only_sync_files: 仅同步文件列表
        log_file: 日志文件路径
        
    Returns:
        bool: 是否应该忽略该文件
    """
    if os.path.abspath(file_path) == os.path.abspath(log_file):
        return True
    
    relative_path = os.path.relpath(file_path, source_dir)
    if only_sync_files:
        return not any(fnmatch(relative_path, pattern) for pattern in only_sync_files)
    
    return any(fnmatch(relative_path, pattern) for pattern in ignore_patterns) 