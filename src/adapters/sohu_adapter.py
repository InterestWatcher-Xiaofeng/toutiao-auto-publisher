"""
搜狐平台适配器

搜狐号发布流程：
1. 进入发布页面: https://mp.sohu.com/mpfe/v3/contentManage/publish
2. 输入标题
3. 输入正文（富文本编辑器）
4. 设置封面（可选）
5. 点击发布按钮
6. 等待发布成功
"""

import asyncio
import random
from typing import Dict, Any
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.adapters.base_adapter import BaseAdapter
from src.core.logger import get_logger
from src.utils.excel_reader import Article

logger = get_logger()


class SohuAdapter(BaseAdapter):
    """搜狐号适配器"""

    PLATFORM_NAME = "sohu"
    # 搜狐号创作平台
    LOGIN_URL = "https://mp.sohu.com/mpfe/v3/login"
    PUBLISH_URL = "https://mp.sohu.com/mpfe/v3/contentManage/publish"
    HOME_URL = "https://mp.sohu.com/mpfe/v3/home"
    
    async def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            page = await self.get_page()
            logger.info(f"[{self.account_name}] 正在检查登录状态...")
            
            # 访问首页
            await page.goto(self.HOME_URL, wait_until='networkidle', timeout=30000)
            await self.random_delay(2, 3)
            
            # 检查是否被重定向到登录页
            current_url = page.url
            if 'login' in current_url:
                logger.info(f"[{self.account_name}] 未登录，当前URL: {current_url}")
                return False
            
            # 检查页面是否有用户相关元素
            try:
                await page.wait_for_selector('.user-info, .avatar, [class*="user"]', timeout=5000)
                logger.info(f"[{self.account_name}] 已登录")
                return True
            except PlaywrightTimeout:
                logger.info(f"[{self.account_name}] 未检测到登录状态")
                return False
                
        except Exception as e:
            logger.error(f"[{self.account_name}] 检查登录状态失败: {e}")
            return False
    
    async def wait_for_login(self) -> bool:
        """等待用户手动登录"""
        try:
            page = await self.get_page()
            logger.info(f"[{self.account_name}] 请在浏览器中手动登录...")

            # 跳转到登录页
            await page.goto(self.LOGIN_URL, wait_until='networkidle', timeout=30000)

            # 等待用户登录成功（最多等待5分钟）
            max_wait = 300
            check_interval = 1  # 每1秒检查一次（更快响应取消）
            waited = 0

            while waited < max_wait:
                # 检查取消标志
                if self._cancelled:
                    logger.info(f"[{self.account_name}] 登录等待已取消")
                    return False

                await asyncio.sleep(check_interval)
                waited += check_interval

                current_url = page.url
                if 'login' not in current_url:
                    logger.info(f"[{self.account_name}] 登录成功！")
                    await self.save_login_state()
                    return True

                if waited % 5 == 0:  # 每5秒打印一次日志
                    logger.debug(f"[{self.account_name}] 等待登录中... ({waited}/{max_wait}秒)")

            logger.warning(f"[{self.account_name}] 登录超时")
            return False

        except Exception as e:
            logger.error(f"[{self.account_name}] 等待登录失败: {e}")
            return False
    
    async def publish_article(self, article: Article) -> Dict[str, Any]:
        """
        发布文章到搜狐号

        完整流程：
        1. 打开发布页面
        2. 等待页面加载完成
        3. 输入标题
        4. 点击并输入正文
        5. 设置封面（如果需要）
        6. 点击发布按钮
        7. 确认发布（如果有弹窗）
        8. 等待发布完成
        """
        try:
            page = await self.get_page()
            logger.info(f"[{self.account_name}] 开始发布文章: {article.title[:30]}...")

            # 步骤1: 打开发布页面
            logger.info(f"[{self.account_name}] 正在打开发布页面...")
            await page.goto(self.PUBLISH_URL, wait_until='domcontentloaded', timeout=60000)
            await self.random_delay(3, 5)

            # 步骤2: 等待编辑器加载
            logger.info(f"[{self.account_name}] 等待编辑器加载...")
            await page.wait_for_load_state('networkidle', timeout=30000)
            await self.random_delay(2, 3)

            # 步骤3: 输入标题
            logger.info(f"[{self.account_name}] 正在输入标题...")
            title_selectors = [
                'textarea[placeholder*="标题"]',
                'input[placeholder*="标题"]',
                '.title-input textarea',
                '.title-input input',
                '[class*="title"] textarea',
                '[class*="title"] input',
            ]

            title_filled = False
            for selector in title_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        await element.click()
                        await self.random_delay(0.3, 0.6)
                        await element.fill(article.title)
                        title_filled = True
                        logger.info(f"[{self.account_name}] 标题输入成功")
                        break
                except PlaywrightTimeout:
                    continue

            if not title_filled:
                raise Exception("无法找到标题输入框")

            await self.random_delay(1, 2)

            # 步骤4: 输入正文
            logger.info(f"[{self.account_name}] 正在输入正文...")
            content_selectors = [
                '.ProseMirror',
                '[contenteditable="true"]',
                '.editor-content',
                '.ql-editor',
                '[class*="editor"] [contenteditable]',
            ]

            content_filled = False
            for selector in content_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        await element.click()
                        await self.random_delay(0.5, 1)
                        await page.keyboard.type(article.content, delay=random.randint(20, 50))
                        content_filled = True
                        logger.info(f"[{self.account_name}] 正文输入成功")
                        break
                except PlaywrightTimeout:
                    continue

            if not content_filled:
                raise Exception("无法找到正文编辑器")

            await self.random_delay(2, 4)

            # 步骤5: 尝试设置封面（可选）
            try:
                await self._select_cover_from_favorites(page)
            except Exception as e:
                logger.warning(f"[{self.account_name}] 封面设置跳过: {e}")

            await self.random_delay(1, 2)

            # 步骤6: 点击发布按钮
            logger.info(f"[{self.account_name}] 正在点击发布按钮...")
            publish_selectors = [
                'button:has-text("发布")',
                '[class*="publish"] button',
                'button[class*="publish"]',
                '.submit-btn',
            ]

            publish_clicked = False
            for selector in publish_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        await element.click()
                        publish_clicked = True
                        logger.info(f"[{self.account_name}] 已点击发布按钮")
                        break
                except PlaywrightTimeout:
                    continue

            if not publish_clicked:
                raise Exception("无法找到发布按钮")

            # 步骤7: 处理可能的确认弹窗
            await self.random_delay(2, 3)
            try:
                confirm_btn = await page.wait_for_selector(
                    'button:has-text("确定"), button:has-text("确认"), .confirm-btn',
                    timeout=3000
                )
                if confirm_btn:
                    await confirm_btn.click()
                    logger.info(f"[{self.account_name}] 已确认发布")
            except PlaywrightTimeout:
                pass

            # 步骤8: 等待发布完成
            await self.random_delay(3, 5)

            await self.save_login_state()

            logger.info(f"[{self.account_name}] ✅ 文章发布成功: {article.title[:30]}...")
            return {'success': True, 'message': '发布成功'}

        except Exception as e:
            error_msg = f"发布失败: {e}"
            logger.error(f"[{self.account_name}] ❌ {error_msg}")
            try:
                await page.screenshot(path=f"error_{self.account_id}_{article.index}.png")
            except:
                pass
            return {'success': False, 'message': error_msg}
    
    async def _select_cover_from_favorites(self, page: Page):
        """从收藏中选择封面图"""
        try:
            logger.info(f"[{self.account_name}] 尝试选择封面图...")
            # 搜狐的封面选择逻辑
            cover_btn = await page.query_selector('[class*="cover"], button:has-text("封面")')
            if cover_btn:
                await cover_btn.click()
                await self.random_delay(1, 2)
            logger.info(f"[{self.account_name}] 封面选择完成")
        except Exception as e:
            logger.warning(f"[{self.account_name}] 选择封面失败: {e}")

