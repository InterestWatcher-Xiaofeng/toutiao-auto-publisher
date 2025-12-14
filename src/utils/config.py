"""
配置管理
"""

import os
import json
from typing import Dict, List, Any

# 项目根目录 - 使用main.py所在目录
# config.py 在 src/utils/ 下，往上2层到达项目根目录
_current_file = os.path.abspath(__file__)
_utils_dir = os.path.dirname(_current_file)  # src/utils
_src_dir = os.path.dirname(_utils_dir)        # src
ROOT_DIR = os.path.dirname(_src_dir)          # 项目根目录

DATA_DIR = os.path.join(ROOT_DIR, 'data')
BROWSER_PROFILES_DIR = os.path.join(DATA_DIR, 'browser_profiles')

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BROWSER_PROFILES_DIR, exist_ok=True)


class Config:
    """配置管理类"""
    
    def __init__(self):
        self.accounts_file = os.path.join(DATA_DIR, 'accounts.json')
        self._accounts = self._load_accounts()
    
    def _load_accounts(self) -> List[Dict[str, Any]]:
        """加载账号配置"""
        if os.path.exists(self.accounts_file):
            with open(self.accounts_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('accounts', [])
        return []
    
    def save_accounts(self):
        """保存账号配置"""
        with open(self.accounts_file, 'w', encoding='utf-8') as f:
            json.dump({'accounts': self._accounts}, f, ensure_ascii=False, indent=4)
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        """获取所有账号"""
        return self._accounts
    
    def get_accounts_by_platform(self, platform: str) -> List[Dict[str, Any]]:
        """按平台获取账号"""
        return [acc for acc in self._accounts if acc['platform'] == platform]
    
    def get_account_by_id(self, account_id: str) -> Dict[str, Any] | None:
        """根据ID获取账号"""
        for acc in self._accounts:
            if acc['id'] == account_id:
                return acc
        return None
    
    def get_profile_dir(self, account_id: str) -> str:
        """获取账号的浏览器配置文件目录"""
        account = self.get_account_by_id(account_id)
        if account:
            profile_dir = os.path.join(BROWSER_PROFILES_DIR, account['profile_dir'])
            os.makedirs(profile_dir, exist_ok=True)
            return profile_dir
        return ""


# 全局配置实例
config = Config()

