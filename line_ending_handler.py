import os
import tempfile

def is_linux_shell_script(file_path):
    """判断文件是否是Linux中的shell脚本文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        bool: 如果是shell脚本文件返回True，否则返回False
    """
    # 需要特殊处理的文件列表
    special_files = ["post-receive"]
    
    # 检查是否是 .sh 文件或在特殊文件列表中
    file_name = os.path.basename(file_path)
    return file_path.endswith('.sh') or file_name in special_files

def convert_line_endings(source_path, target_os='linux'):
    """转换文件的行尾符号为目标操作系统格式
    
    Args:
        source_path: 源文件路径
        target_os: 目标操作系统，默认为'linux'
        
    Returns:
        tuple: (文件路径, 是否创建了临时文件)
            - 如果创建了临时文件，返回临时文件路径和True
            - 如果未创建临时文件，返回原文件路径和False
    """
    # 只处理shell脚本文件
    if not is_linux_shell_script(source_path):
        return source_path, False
        
    # 读取文件内容
    with open(source_path, 'rb') as f:
        content = f.read()
        
    # 检查是否需要转换行尾符号
    if b'\r' not in content:  # 既检查\r\n也检查\r
        return source_path, False
        
    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.sh')
    temp_path = temp_file.name
    temp_file.close()
    
    print(f"转换行尾格式: {source_path}")
    
    # 先将所有\r\n替换为\n，再将剩余的\r替换为\n
    content = content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    
    # 写入转换后的内容到临时文件
    with open(temp_path, 'wb') as f:
        f.write(content)
        
    # 返回临时文件路径和创建临时文件的标志
    return temp_path, True

def cleanup_temp_file(temp_path, is_temp=False):
    """清理临时文件
    
    Args:
        temp_path: 临时文件路径
        is_temp: 是否为临时文件，如果为True则删除文件
    """
    if is_temp and os.path.exists(temp_path):
        os.remove(temp_path)

def print_shell_script_commands(file_path, source_dir):
    """打印shell脚本文件的特殊命令
    
    Args:
        file_path: 文件路径
        source_dir: 源目录
    """
    # 检查是否是shell脚本文件
    if is_linux_shell_script(file_path):
        # 使用相对路径，并转换为正斜杠分隔符
        relative_path = os.path.relpath(file_path, source_dir).replace('\\', '/')
        print(f"sed -i 's/\\r$//' {relative_path}")
        print(f"chmod +x {relative_path}") 