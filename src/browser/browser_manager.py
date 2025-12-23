"""
浏览器管理模块
使用Playwright管理多个独立的浏览器配置文件
"""

import asyncio
import os
from typing import Dict, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from src.core.logger import get_logger
from src.utils.config import BROWSER_PROFILES_DIR

logger = get_logger()


class BrowserManager:
    """浏览器管理器 - 管理多个独立的浏览器上下文"""

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: Dict[str, BrowserContext] = {}
        self._pages: Dict[str, Page] = {}
        self._initialized = False
        self._current_loop = None  # 记录当前的event loop

    async def initialize(self):
        """初始化Playwright"""
        current_loop = asyncio.get_running_loop()  # 使用 get_running_loop 更可靠

        logger.debug(f"initialize() 调用 - current_loop={id(current_loop)}, saved_loop={id(self._current_loop) if self._current_loop else None}")

        # 如果loop变了，需要重新初始化（跳过清理，因为旧资源属于旧loop）
        if self._current_loop is not None and self._current_loop != current_loop:
            logger.info(f"检测到event loop变化，重新初始化Playwright... (old={id(self._current_loop)}, new={id(current_loop)})")
            await self._force_reinitialize(skip_cleanup=True)
            self._current_loop = current_loop
            return

        # 检查是否已经初始化且仍然有效
        if self._initialized and self._playwright and self._browser:
            try:
                # 测试浏览器是否仍然可用
                if self._browser.is_connected():
                    logger.debug("浏览器已连接，跳过初始化")
                    return
            except Exception as e:
                logger.debug(f"浏览器连接检查失败: {e}")
                pass

        # 需要重新初始化
        await self._force_reinitialize(skip_cleanup=False)
        self._current_loop = current_loop

    async def reinitialize_for_new_loop(self):
        """在新的 event loop 中强制重新初始化

        当从不同的 QThread/event loop 调用时使用此方法，
        确保 Playwright 资源在当前 event loop 中正确初始化。
        """
        current_loop = asyncio.get_running_loop()

        # 如果 event loop 没变且浏览器已连接，跳过
        if (self._current_loop == current_loop and
            self._initialized and self._browser and
            self._browser.is_connected()):
            logger.info("浏览器已在当前 event loop 中初始化，跳过重新初始化")
            return

        logger.info(f"为新的 event loop 重新初始化浏览器...")
        # 丢弃旧引用（不尝试清理，因为它们属于旧 event loop）
        await self._force_reinitialize(skip_cleanup=True)
        self._current_loop = current_loop

    async def _force_reinitialize(self, skip_cleanup: bool = False):
        """强制重新初始化Playwright

        Args:
            skip_cleanup: 是否跳过清理旧资源（当event loop变化时应该跳过）
        """
        if not skip_cleanup:
            # 先清理旧资源
            try:
                if self._browser:
                    await self._browser.close()
            except:
                pass
            try:
                if self._playwright:
                    await self._playwright.stop()
            except:
                pass
        else:
            logger.info("跳过清理旧资源（event loop已变化）")

        # 丢弃旧引用
        self._browser = None
        self._playwright = None
        self._contexts = {}
        self._pages = {}

        logger.info("正在初始化Playwright...")
        self._playwright = await async_playwright().start()
        # 使用Chromium浏览器
        self._browser = await self._playwright.chromium.launch(
            headless=False,  # 显示浏览器窗口，便于调试和手动登录
            args=[
                '--disable-blink-features=AutomationControlled',  # 隐藏自动化特征
                '--no-sandbox',
            ]
        )
        self._initialized = True
        logger.info("Playwright初始化完成")
    
    async def get_context(self, account_id: str, profile_dir: str) -> BrowserContext:
        """
        获取或创建指定账号的浏览器上下文

        Args:
            account_id: 账号ID
            profile_dir: 配置文件目录名

        Returns:
            浏览器上下文
        """
        # 首先确保浏览器已初始化（这会处理 event loop 变化的情况）
        await self.initialize()

        # 检查现有上下文是否仍然有效
        if account_id in self._contexts:
            try:
                # 测试上下文是否仍然有效
                context = self._contexts[account_id]
                # 如果上下文已关闭，会抛出异常
                pages = context.pages
                return context
            except:
                # 上下文已失效，需要重新创建
                del self._contexts[account_id]
                if account_id in self._pages:
                    del self._pages[account_id]

        # 创建配置文件目录
        storage_path = os.path.join(BROWSER_PROFILES_DIR, profile_dir)
        os.makedirs(storage_path, exist_ok=True)

        storage_state_file = os.path.join(storage_path, 'storage_state.json')

        # 创建持久化上下文
        context_options = {
            'viewport': {'width': 1280, 'height': 800},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

        # 如果存在存储状态文件，加载它
        if os.path.exists(storage_state_file):
            context_options['storage_state'] = storage_state_file
            logger.info(f"加载已保存的登录状态: {account_id}")

        context = await self._browser.new_context(**context_options)
        self._contexts[account_id] = context

        logger.info(f"创建浏览器上下文: {account_id}")
        return context

    async def get_page(self, account_id: str, profile_dir: str) -> Page:
        """获取或创建指定账号的页面"""
        # 检查现有页面是否仍然有效
        if account_id in self._pages:
            try:
                page = self._pages[account_id]
                if not page.is_closed():
                    return page
            except:
                pass
            # 页面已失效
            del self._pages[account_id]

        context = await self.get_context(account_id, profile_dir)
        page = await context.new_page()
        self._pages[account_id] = page

        return page
    
    async def save_storage_state(self, account_id: str, profile_dir: str):
        """保存浏览器状态（Cookie等）"""
        if account_id not in self._contexts:
            return
        
        storage_path = os.path.join(BROWSER_PROFILES_DIR, profile_dir)
        storage_state_file = os.path.join(storage_path, 'storage_state.json')
        
        await self._contexts[account_id].storage_state(path=storage_state_file)
        logger.info(f"已保存登录状态: {account_id}")
    
    async def close_context(self, account_id: str):
        """关闭指定账号的上下文"""
        if account_id in self._pages:
            await self._pages[account_id].close()
            del self._pages[account_id]
        
        if account_id in self._contexts:
            await self._contexts[account_id].close()
            del self._contexts[account_id]
            logger.info(f"已关闭浏览器上下文: {account_id}")
    
    async def close_all(self):
        """关闭所有资源"""
        for account_id in list(self._pages.keys()):
            try:
                await self._pages[account_id].close()
            except:
                pass
        self._pages.clear()

        for account_id in list(self._contexts.keys()):
            try:
                await self._contexts[account_id].close()
            except:
                pass
        self._contexts.clear()

        if self._browser:
            try:
                await self._browser.close()
            except:
                pass
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except:
                pass
            self._playwright = None

        self._initialized = False
        self._current_loop = None
        logger.info("已关闭所有浏览器资源")

    async def cleanup(self):
        """清理浏览器资源（登录完成后调用）"""
        await self.close_all()

    async def open_standalone_browser(self, account_id: str, profile_dir: str, start_url: str = None):
        """打开独立浏览器（不受程序管理，用户可以一直使用）

        Args:
            account_id: 账号ID
            profile_dir: 配置文件目录名
            start_url: 启动时打开的URL（可选）

        Returns:
            打开的Page对象（仅用于初始导航，之后不再管理）
        """
        # 创建新的playwright实例（独立于主程序）
        standalone_playwright = await async_playwright().start()

        # 启动独立浏览器
        standalone_browser = await standalone_playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ]
        )

        # 创建配置文件目录
        storage_path = os.path.join(BROWSER_PROFILES_DIR, profile_dir)
        os.makedirs(storage_path, exist_ok=True)

        storage_state_file = os.path.join(storage_path, 'storage_state.json')

        # 创建上下文选项
        context_options = {
            'viewport': {'width': 1280, 'height': 800},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

        # 如果存在存储状态文件，加载它
        if os.path.exists(storage_state_file):
            context_options['storage_state'] = storage_state_file
            logger.info(f"独立浏览器加载登录状态: {account_id}")

        context = await standalone_browser.new_context(**context_options)
        page = await context.new_page()

        # 如果指定了URL，导航到该页面
        if start_url:
            await page.goto(start_url, wait_until='domcontentloaded')

        logger.info(f"已打开独立浏览器: {account_id}")

        # 注意：不保存这个浏览器的引用，让它独立运行
        # 用户手动关闭浏览器时，资源会自动释放
        return page


# 全局浏览器管理器实例
browser_manager = BrowserManager()

