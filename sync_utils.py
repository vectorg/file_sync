import os
import subprocess
from datetime import datetime
import json
from fnmatch import fnmatch
import paramiko
from line_ending_handler import convert_line_endings, cleanup_temp_file

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
        print(f"复制文件: {source_path} -> {destination_path}")
        shutil.copy2(source_path, destination_path)
    except Exception as e:
        raise

def sync_to_remote(source_path, remote_path, target):
    """同步到远程服务器，有密码时使用paramiko，无密码时使用scp"""
    file_path = None
    is_temp_file = False
    
    try:
        server = target['server'].split('@')[1]
        if '#' in server:  # 如果服务器地址中包含端口，需要去掉
            server = server.split('#')[0]
        
        # 转换行尾符号
        file_path, is_temp_file = convert_line_endings(source_path, target_os='linux')
        
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
                mkdir_cmd = f"mkdir -p '{remote_dir}'"
                print(f"执行远程命令: {mkdir_cmd}")
                ssh.exec_command(mkdir_cmd)
                print(f"上传文件: {file_path} -> {target['server']}:{remote_path}")
                sftp.put(file_path, remote_path)
            finally:
                ssh.close()
        
        # 如果没有提供密码，使用scp（依赖SSH密钥），不指定端口
        else:
            # 创建远程目录
            remote_dir = os.path.dirname(remote_path)
            mkdir_cmd = f"ssh {target['server']} \"mkdir -p '{remote_dir}'\""
            print(f"执行命令: {mkdir_cmd}")
            subprocess.run(mkdir_cmd, shell=True, check=True)
            
            # 执行scp命令
            scp_cmd = f"scp \"{file_path}\" \"{target['server']}:{remote_path}\""
            print(f"执行命令: {scp_cmd}")
            subprocess.run(scp_cmd, shell=True, check=True)
            
    except (subprocess.CalledProcessError, paramiko.SSHException) as e:
        print(f"远程同步失败: {e}")
        raise
    finally:
        # 清理临时文件
        if file_path and is_temp_file:
            cleanup_temp_file(file_path, is_temp_file)

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

def delete_from_local(destination_path):
    """从本地目标目录删除文件
    
    Args:
        destination_path: 目标文件路径
    """
    try:
        if os.path.exists(destination_path):
            print(f"删除本地文件: {destination_path}")
            os.remove(destination_path)
            # 如果目录为空，删除目录
            dir_path = os.path.dirname(destination_path)
            if os.path.exists(dir_path) and not os.listdir(dir_path):
                print(f"删除空目录: {dir_path}")
                os.rmdir(dir_path)
    except Exception as e:
        print(f"删除本地文件失败: {e}")
        raise

def delete_from_remote(remote_path, target):
    """从远程服务器删除文件
    
    Args:
        remote_path: 远程文件路径
        target: 目标配置
    """
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
                
                # 删除远程文件
                rm_cmd = f"rm -f '{remote_path}'"
                print(f"执行远程命令: {rm_cmd}")
                ssh.exec_command(rm_cmd)
                
                # 如果目录为空，删除目录
                remote_dir = os.path.dirname(remote_path)
                rmdir_cmd = f"rmdir '{remote_dir}' 2>/dev/null || true"
                print(f"执行远程命令: {rmdir_cmd}")
                ssh.exec_command(rmdir_cmd)
            finally:
                ssh.close()
        
        # 如果没有提供密码，使用ssh命令（依赖SSH密钥）
        else:
            # 删除远程文件
            rm_cmd = f"ssh {target['server']} \"rm -f '{remote_path}'\""
            print(f"执行命令: {rm_cmd}")
            subprocess.run(rm_cmd, shell=True, check=True)
            
            # 如果目录为空，删除目录
            remote_dir = os.path.dirname(remote_path)
            rmdir_cmd = f"ssh {target['server']} \"rmdir '{remote_dir}' 2>/dev/null || true\""
            print(f"执行命令: {rmdir_cmd}")
            subprocess.run(rmdir_cmd, shell=True, check=True)
            
    except (subprocess.CalledProcessError, paramiko.SSHException) as e:
        print(f"删除远程文件失败: {e}")
        raise

def delete_from_local_dir(destination_path):
    """从本地目标目录删除目录
    
    Args:
        destination_path: 目标目录路径
    """
    try:
        if os.path.exists(destination_path):
            import shutil
            print(f"删除本地目录: {destination_path}")
            shutil.rmtree(destination_path)
    except Exception as e:
        print(f"删除本地目录失败: {e}")
        raise

def delete_from_remote_dir(remote_path, target):
    """从远程服务器删除目录
    
    Args:
        remote_path: 远程目录路径
        target: 目标配置
    """
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
                
                # 删除远程目录
                rm_cmd = f"rm -rf '{remote_path}'"
                print(f"执行远程命令: {rm_cmd}")
                ssh.exec_command(rm_cmd)
            finally:
                ssh.close()
        
        # 如果没有提供密码，使用ssh命令（依赖SSH密钥）
        else:
            # 删除远程目录
            rm_cmd = f"ssh {target['server']} \"rm -rf '{remote_path}'\""
            print(f"执行命令: {rm_cmd}")
            subprocess.run(rm_cmd, shell=True, check=True)
            
    except (subprocess.CalledProcessError, paramiko.SSHException) as e:
        print(f"删除远程目录失败: {e}")
        raise 