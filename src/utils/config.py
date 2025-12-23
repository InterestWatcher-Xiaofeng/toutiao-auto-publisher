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

    def update_account_nickname(self, account_id: str, nickname: str):
        """更新账号昵称并保存到配置文件（登录后自动获取的昵称）

        Args:
            account_id: 账号ID
            nickname: 新昵称
        """
        for acc in self._accounts:
            if acc['id'] == account_id:
                # 获取平台前缀
                platform = acc.get('platform', '')
                platform_prefixes = {"toutiao": "今日头条", "sohu": "搜狐", "baijiahao": "百家号"}
                platform_prefix = platform_prefixes.get(platform, platform)

                # 更新名称
                acc['name'] = f"{platform_prefix}-{nickname}"
                acc['nickname'] = nickname  # 保存原始昵称

                # 保存到文件
                self.save_accounts()
                break

    def update_account_name(self, account_id: str, new_name: str):
        """更新账号显示名称（用户手动修改的完整名称）

        Args:
            account_id: 账号ID
            new_name: 新的完整显示名称
        """
        for acc in self._accounts:
            if acc['id'] == account_id:
                acc['name'] = new_name
                self.save_accounts()
                break

    def reorder_accounts(self, new_order: list):
        """重新排序账号列表

        Args:
            new_order: 账号ID的新顺序列表
        """
        # 创建ID到账号的映射
        account_map = {acc['id']: acc for acc in self._accounts}

        # 按新顺序重建列表
        reordered = []
        for account_id in new_order:
            if account_id in account_map:
                reordered.append(account_map[account_id])

        # 添加不在新顺序中的账号（防止丢失）
        for acc in self._accounts:
            if acc['id'] not in new_order:
                reordered.append(acc)

        self._accounts = reordered
        self.save_accounts()

    def add_account(self, platform: str) -> Dict[str, Any]:
        """添加新账号

        Args:
            platform: 平台名称 ('toutiao', 'sohu' 或 'baijiahao')

        Returns:
            新创建的账号信息字典
        """
        # 计算该平台已有账号数量，生成新ID
        platform_accounts = [acc for acc in self._accounts if acc['platform'] == platform]
        new_index = len(platform_accounts) + 1

        # 生成账号ID和目录名
        account_id = f"{platform}_{new_index}"
        profile_dir = f"{platform}_account{new_index}"

        # 确保ID不重复（防止删除后重新添加冲突）
        existing_ids = {acc['id'] for acc in self._accounts}
        while account_id in existing_ids:
            new_index += 1
            account_id = f"{platform}_{new_index}"
            profile_dir = f"{platform}_account{new_index}"

        # 生成账号名称
        platform_prefixes = {"toutiao": "今日头条", "sohu": "搜狐", "baijiahao": "百家号"}
        platform_prefix = platform_prefixes.get(platform, platform)
        account_name = f"{platform_prefix}-账号{new_index}"

        # 创建浏览器配置目录
        full_profile_dir = os.path.join(BROWSER_PROFILES_DIR, profile_dir)
        os.makedirs(full_profile_dir, exist_ok=True)

        # 创建账号信息
        new_account = {
            "id": account_id,
            "platform": platform,
            "name": account_name,
            "profile_dir": profile_dir,
            "enabled": True
        }

        # 添加到列表并保存
        self._accounts.append(new_account)
        self.save_accounts()

        return new_account

    def delete_account(self, account_id: str) -> bool:
        """删除账号

        Args:
            account_id: 账号ID

        Returns:
            是否删除成功
        """
        import shutil

        # 查找账号
        account = self.get_account_by_id(account_id)
        if not account:
            return False

        # 从列表中移除
        self._accounts = [acc for acc in self._accounts if acc['id'] != account_id]
        self.save_accounts()

        # 删除浏览器配置目录
        profile_dir = account.get('profile_dir', '')
        if profile_dir:
            full_profile_dir = os.path.join(BROWSER_PROFILES_DIR, profile_dir)
            if os.path.exists(full_profile_dir):
                try:
                    shutil.rmtree(full_profile_dir)
                except Exception:
                    pass  # 删除失败不影响账号删除

        return True


# 全局配置实例
config = Config()

