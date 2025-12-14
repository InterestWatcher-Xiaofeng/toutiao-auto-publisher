"""
平台适配器基类
所有平台适配器都继承此类
"""

import asyncio
import random
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from playwright.async_api import Page

from src.core.logger import get_logger
from src.utils.excel_reader import Article

logger = get_logger()


class BaseAdapter(ABC):
    """平台适配器基类"""

    # 平台名称
    PLATFORM_NAME = "base"
    # 登录页面URL
    LOGIN_URL = ""
    # 发布页面URL
    PUBLISH_URL = ""

    # 类变量：存储所有browser_manager实例
    _browser_managers = {}

    def __init__(self, account_id: str, profile_dir: str, account_name: str, browser_manager=None):
        """
        初始化适配器

        Args:
            account_id: 账号ID
            profile_dir: 浏览器配置文件目录
            account_name: 账号显示名称
            browser_manager: 可选的浏览器管理器实例
        """
        self.account_id = account_id
        self.profile_dir = profile_dir
        self.account_name = account_name
        self._page: Optional[Page] = None
        self._cancelled = False  # 取消标志

        # 使用传入的browser_manager，或者导入全局的
        if browser_manager:
            self._browser_manager = browser_manager
        else:
            from src.browser.browser_manager import browser_manager as bm
            self._browser_manager = bm

    def cancel(self):
        """标记取消"""
        self._cancelled = True

    async def get_page(self) -> Page:
        """获取页面实例"""
        from src.core.logger import get_logger
        logger = get_logger()

        if self._page is None or self._page.is_closed():
            logger.info(f"[{self.account_name}] 正在创建新页面...")
            self._page = await self._browser_manager.get_page(self.account_id, self.profile_dir)
            logger.info(f"[{self.account_name}] 页面创建成功")
        return self._page
    
    async def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """随机延迟，模拟人工操作"""
        delay = random.uniform(min_seconds, max_seconds)
        logger.debug(f"随机延迟 {delay:.2f} 秒")
        await asyncio.sleep(delay)
    
    async def type_like_human(self, page: Page, selector: str, text: str):
        """模拟人工打字"""
        element = await page.wait_for_selector(selector, timeout=10000)
        if element:
            await element.click()
            await self.random_delay(0.3, 0.8)
            # 逐字输入，模拟打字
            for char in text:
                await element.type(char, delay=random.randint(50, 150))
    
    @abstractmethod
    async def check_login_status(self) -> bool:
        """
        检查登录状态
        
        Returns:
            是否已登录
        """
        pass
    
    @abstractmethod
    async def wait_for_login(self) -> bool:
        """
        等待用户手动登录
        
        Returns:
            登录是否成功
        """
        pass
    
    @abstractmethod
    async def publish_article(self, article: Article) -> Dict[str, Any]:
        """
        发布文章
        
        Args:
            article: 文章对象
            
        Returns:
            发布结果 {'success': bool, 'message': str}
        """
        pass
    
    async def save_login_state(self):
        """保存登录状态"""
        await self._browser_manager.save_storage_state(self.account_id, self.profile_dir)

    async def close(self):
        """关闭适配器 - 不关闭浏览器，保持打开状态供用户查看"""
        # 注意：不再关闭浏览器上下文，让用户可以查看结果
        # 浏览器将在程序退出时由用户手动关闭
        pass

