import os
from collections import defaultdict
from main import main

CWD = r"C:\Users\xx\Documents\projects\111"

# 远程服务器配置 (用户名, IP, 路径, 密码, 端口)
SERVER_CONFIG = ("ubuntu", "192.168.11.11", "/home/workspace/projects/111", "123456", None)

# 获取当前脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取应用数据目录
APP_DATA_DIR = os.path.join(os.getenv('APPDATA') or os.path.expanduser('~/.local/share'), 'FileSyncLog')
# 确保目录存在
os.makedirs(APP_DATA_DIR, exist_ok=True)

# 默认配置
default_config = {
    'source_dir': '', # 源目录
    'targets': [], # 目标目录
    'log_file': os.path.join(APP_DATA_DIR, '_sync_log.txt'), # 同步日志文件
    'last_sync_file': os.path.join(SCRIPT_DIR, '_last_sync.json'), # 上次同步时间记录文件
    'ignore_patterns': [
        "__pycache__/*","*.pyc","*.tmp", # 缓存文件
        "_file_sync*/*","_sync_log.txt","_last_sync.json","*.log", # 同步日志相关文件
        ".git/*",".gitignore", # git 相关
    ],
    'only_sync_files': [],    # 仅同步指定文件列表（如果为空则使用 IGNORE_PATTERNS）
    # mode: 0=不处理, 1=预览, 2=一次性智能同步, 3=智能同步并监控, 4=完整同步并监控, 11=预览并更新同步时间
    'mode': 3
}

# 使用带默认值的 defaultdict
CONFIGS = defaultdict(lambda: default_config.copy())

# 配置0
CONFIGS['main'] = default_config.copy() | {
    'source_dir': CWD,  # 使用当前工作目录
    'targets': [
        # 本地路径示例
        # r"C:\Users\xx\AppData\Local\Temp\Mxt242\tmp\home_xx",
        # 远程路径现在使用元组格式
        SERVER_CONFIG,
        # ("ubuntu", "192.168.11.11", "/other/path", "password", None),  # 使用默认端口
    ],
    'ignore_patterns': default_config['ignore_patterns'] + [
        "history/*","docs/*", # 历史文件、文档相关、数据文件
        "data/*",
        "*/_dev/*","*/_docs/*","*/_history/*",
    ],
    'only_sync_files': [
        # 示例：只同步这些文件
        # "docker-compose.yaml",
        # ".env",
    ]
}

main(CONFIGS)
