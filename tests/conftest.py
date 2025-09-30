import sys
from pathlib import Path

from dotenv import load_dotenv

# 添加项目根目录到 PATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量（仅用于集成测试）
load_dotenv(project_root / '.env.local')
load_dotenv(project_root / '.env')
