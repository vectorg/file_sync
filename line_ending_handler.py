import os
import tempfile

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
    # 只处理sh文件
    if not source_path.endswith('.sh'):
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