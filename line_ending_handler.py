import os
import tempfile

def convert_line_endings(source_path, target_os='linux'):
    """转换sh文件的行尾符号为LF"""
    if not source_path.endswith('.sh'):
        return source_path, False
        
    with open(source_path, 'rb') as f:
        content = f.read()
        
    if b'\r' not in content:  # 既检查\r\n也检查\r
        return source_path, False
        
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.sh')
    temp_path = temp_file.name
    temp_file.close()
    
    print(f"转换行尾格式: {source_path}")
    
    # 先将所有\r\n替换为\n，再将剩余的\r替换为\n
    content = content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    
    with open(temp_path, 'wb') as f:
        f.write(content)
        
    return temp_path, True

def cleanup_temp_file(temp_path, is_temp=False):
    """清理临时文件"""
    if is_temp and os.path.exists(temp_path):
        os.remove(temp_path) 