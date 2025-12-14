"""今日头条平台适配器 - 完整版。

实现完整的今日头条文章发布流程：
1. 打开发布页面
2. 填写标题
3. 填写正文
4. 选择封面（从素材库）
5. 点击预览并发布
6. 确认发布
"""

import asyncio
from typing import Dict, Any

from src.adapters.base_adapter import BaseAdapter
from src.core.logger import get_logger
from src.utils.excel_reader import Article


logger = get_logger()


# 今日头条页面元素选择器
class ToutiaoSelectors:
    """今日头条页面元素选择器"""
    # 标题输入框
    TITLE_INPUT = "textarea"
    # 正文编辑器
    CONTENT_EDITOR = ".ProseMirror"

    # 选择封面区域
    COVER_SELECT_AREA = ".article-cover-images-wrap .article-cover-images > div > div > div > div"

    # 素材抽屉中的"我的素材"标签（第4个标签）
    MY_MATERIAL_TAB = ".byte-drawer .byte-tabs-header-nav div > div > div > div:nth-child(4)"

    # 素材库中的第一张图片
    MATERIAL_FIRST_IMAGE = ".byte-drawer .ReactVirtualized__List > div > div > div > div:nth-child(1) > div > div > span.img-span"

    # 素材选择确定按钮
    MATERIAL_CONFIRM_BTN = ".byte-drawer .footer button.byte-btn-primary > span"

    # 发布按钮（页面底部的"预览并发布"按钮）
    PUBLISH_BTN = "#root button.publish-btn.publish-btn-last > span"

    # 确认发布按钮
    CONFIRM_PUBLISH_BTN = "#root button.publish-btn.publish-btn-last > span"


class ToutiaoAdapter(BaseAdapter):
    """Minimal stub adapter for Toutiao.

    It satisfies Scheduler imports and method calls but does not drive a browser yet.
    """

    PLATFORM_NAME = "toutiao"
    LOGIN_URL = "https://mp.toutiao.com/auth/page/login"
    PUBLISH_URL = "https://mp.toutiao.com/profile_v4/graphic/publish"
    HOME_URL = "https://mp.toutiao.com/profile_v4/index"

    async def check_login_status(self) -> bool:
        """**不再访问任何网页，只用当前页面 URL 来快速判断是否登录。**

        这么改的原因：
        - 之前这里会 `goto` 头条首页/发文页，网络慢时就会卡 30 多秒，你就看到
          「卡在检查登录状态」；
        - 现在这里只做两件事：
          1. 确保创建页面（让浏览器一定弹出来）；
          2. 看当前 URL 里有没有 `login`/`auth` 来判断是否登录；

        规则：
        - 如果当前是空白页（about:blank）→ 认为「未登录」，让后面的 `wait_for_login`
          去真正打开登录页；
        - 如果 URL 里包含 `login` 或 `auth` → 认为「未登录」；
        - 其它情况 → 认为「已登录」。
        """

        page = await self.get_page()  # 会触发 BrowserManager 启动浏览器
        logger.info(f"[{self.account_name}] 正在检查登录状态（Toutiao 简化版）...")

        current_url = page.url or ""
        logger.info(f"[{self.account_name}] 当前URL: {current_url}")

        # 初次创建 page 时一般是 about:blank，这里直接当成未登录，去走手动登录流程
        if not current_url or current_url.startswith("about:blank"):
            logger.info(f"[{self.account_name}] 当前为空白页，视为【未登录】")
            return False

        if "login" in current_url or "auth" in current_url:
            logger.info(f"[{self.account_name}] 判断为【未登录】（命中 login/auth）")
            return False

        logger.info(f"[{self.account_name}] 判断为【已登录】（URL 未包含 login/auth）")
        return True

    async def get_nickname(self) -> str:
        """获取当前登录账号的昵称。

        Returns:
            str: 账号昵称，获取失败返回空字符串
        """
        try:
            page = await self.get_page()

            # 访问首页获取昵称
            await page.goto(self.HOME_URL, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1)

            # 尝试多个可能的选择器获取昵称
            selectors = [
                ".user-info-name",  # 用户信息区域的名称
                ".header-user-name",  # 头部用户名
                ".account-name",  # 账号名称
                ".mp-header-user-info .name",  # 头条创作者后台用户名
            ]

            for selector in selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        nickname = await element.text_content()
                        if nickname and nickname.strip():
                            nickname = nickname.strip()
                            logger.info(f"[{self.account_name}] 获取到昵称: {nickname}")
                            return nickname
                except Exception:
                    continue

            # 如果上面的选择器都找不到，尝试从页面标题或其他地方获取
            logger.warning(f"[{self.account_name}] 无法获取昵称，使用默认名称")
            return ""

        except Exception as e:
            logger.error(f"[{self.account_name}] 获取昵称失败: {e}")
            return ""

    async def wait_for_login(self) -> tuple:
        """在浏览器里打开登录页，等待你手动登录（简化版）。

        Returns:
            tuple: (success: bool, nickname: str) 登录是否成功以及账号昵称
        """

        page = await self.get_page()
        logger.info(f"[{self.account_name}] 请在弹出的浏览器中手动登录 Toutiao...")

        try:
            await page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.error(f"[{self.account_name}] 打开登录页失败: {e}")
            return (False, "")

        # 简单轮询 URL 是否还包含 login/auth，最长 5 分钟
        max_wait = 300
        interval = 1
        waited = 0

        while waited < max_wait:
            if self._cancelled:
                logger.info(f"[{self.account_name}] 登录等待已取消")
                return (False, "")

            await asyncio.sleep(interval)
            waited += interval

            current_url = page.url or ""
            if "login" not in current_url and "auth" not in current_url:
                logger.info(f"[{self.account_name}] 检测到已登录，当前URL: {current_url}")
                try:
                    await self.save_login_state()
                except Exception:
                    pass

                # 获取昵称
                nickname = await self.get_nickname()
                return (True, nickname)

            if waited % 5 == 0:
                logger.debug(
                    f"[{self.account_name}] 等待登录中... ({waited}/{max_wait} 秒) 当前URL: {current_url}",
                )

        logger.warning(f"[{self.account_name}] 登录等待超时")
        return (False, "")

    async def publish_article(self, article: Article) -> Dict[str, Any]:
        """完整的今日头条文章发布流程。

        步骤：
        1. 打开发布页面
        2. 填写标题
        3. 填写正文
        4. 选择封面（从素材库选择第一张）
        5. 点击预览并发布
        6. 确认发布
        """
        try:
            page = await self.get_page()
            title = getattr(article, 'title', '')
            content = getattr(article, 'content', '')

            logger.info(f"[{self.account_name}] 开始发布文章: {title[:50]}...")

            # 1. 打开发布页面
            logger.info(f"[{self.account_name}] 正在打开发布页面: {self.PUBLISH_URL}")
            logger.info(f"[{self.account_name}] 当前页面状态 - URL: {page.url}, is_closed: {page.is_closed()}")
            try:
                # 使用 commit 等待策略，仅等待页面开始导航
                await page.goto(self.PUBLISH_URL, wait_until="commit", timeout=30000)
                logger.info(f"[{self.account_name}] 页面导航已开始，等待加载...")
                # 然后等待DOM加载
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception as goto_err:
                logger.error(f"[{self.account_name}] 打开发布页面超时: {goto_err}")
                return {"success": False, "message": f"打开发布页面超时: {goto_err}"}
            logger.info(f"[{self.account_name}] 已打开发布页面, 当前URL: {page.url}")
            await self.random_delay(2, 3)

            # 2. 等待标题输入框出现
            try:
                await page.wait_for_selector(ToutiaoSelectors.TITLE_INPUT, timeout=15000)
            except Exception as e:
                logger.error(f"[{self.account_name}] 等待标题输入框超时: {e}")
                return {"success": False, "message": f"等待页面加载超时: {e}"}

            # 3. 点击标题区域（关闭可能的弹窗）
            try:
                await page.click(ToutiaoSelectors.TITLE_INPUT, force=True)
                await self.random_delay(0.5, 1)
            except Exception:
                pass

            # 4. 填写标题
            logger.info(f"[{self.account_name}] 正在填写标题...")
            try:
                await page.fill(ToutiaoSelectors.TITLE_INPUT, title)
                await self.random_delay(1, 2)
            except Exception as e:
                logger.error(f"[{self.account_name}] 填写标题失败: {e}")
                return {"success": False, "message": f"填写标题失败: {e}"}

            # 5. 填写正文
            logger.info(f"[{self.account_name}] 正在填写正文...")
            try:
                # 点击正文编辑器
                await page.click(ToutiaoSelectors.CONTENT_EDITOR, force=True)
                await self.random_delay(0.5, 1)
                # 填写正文内容
                await page.fill(ToutiaoSelectors.CONTENT_EDITOR, content)
                await self.random_delay(1, 2)
            except Exception as e:
                logger.error(f"[{self.account_name}] 填写正文失败: {e}")
                return {"success": False, "message": f"填写正文失败: {e}"}

            # 6. 选择封面（从素材库）
            logger.info(f"[{self.account_name}] 正在选择封面...")
            try:
                await self._select_cover_from_material(page)
            except Exception as e:
                logger.warning(f"[{self.account_name}] 选择封面失败（继续发布）: {e}")
                # 封面选择失败不阻止发布

            # 7. 点击发布按钮
            logger.info(f"[{self.account_name}] 正在点击发布按钮...")
            try:
                publish_btn = await page.wait_for_selector(ToutiaoSelectors.PUBLISH_BTN, timeout=10000)
                if publish_btn:
                    await publish_btn.click()
                    logger.info(f"[{self.account_name}] ✓ 已点击发布按钮")
                    await self.random_delay(2, 3)
                else:
                    logger.error(f"[{self.account_name}] 未找到发布按钮")
                    return {"success": False, "message": "未找到发布按钮"}
            except Exception as e:
                logger.error(f"[{self.account_name}] 点击发布按钮失败: {e}")
                return {"success": False, "message": f"点击发布按钮失败: {e}"}

            # 8. 确认发布（如果有确认弹窗）
            try:
                confirm_btn = await page.wait_for_selector(
                    ToutiaoSelectors.CONFIRM_PUBLISH_BTN,
                    timeout=5000
                )
                if confirm_btn:
                    await confirm_btn.click()
                    logger.info(f"[{self.account_name}] 已点击确认发布")
                    await self.random_delay(2, 3)
            except Exception:
                # 没有确认弹窗也正常
                pass

            # 9. 等待发布完成
            await asyncio.sleep(3)

            logger.info(f"[{self.account_name}] ✅ 文章发布完成: {title[:30]}...")
            return {"success": True, "message": "发布成功"}

        except Exception as e:
            logger.error(f"[{self.account_name}] 发布文章异常: {e}")
            return {"success": False, "message": f"发布异常: {e}"}

    async def _select_cover_from_material(self, page):
        """从素材库选择封面图片"""
        # 1. 点击选择封面区域，打开素材抽屉
        logger.info(f"[{self.account_name}] 正在点击封面选择区域...")
        try:
            cover_area = await page.wait_for_selector(
                ToutiaoSelectors.COVER_SELECT_AREA,
                timeout=5000
            )
            if cover_area:
                await cover_area.click()
                logger.info(f"[{self.account_name}] ✓ 已点击封面选择区域")
                await self.random_delay(1, 2)
            else:
                logger.warning(f"[{self.account_name}] 未找到封面选择区域")
                return
        except Exception as e:
            logger.warning(f"[{self.account_name}] 点击封面选择区域失败: {e}")
            return

        # 2. 点击"我的素材"标签
        logger.info(f"[{self.account_name}] 正在点击'我的素材'标签...")
        try:
            material_tab = await page.wait_for_selector(
                ToutiaoSelectors.MY_MATERIAL_TAB,
                timeout=5000
            )
            if material_tab:
                await material_tab.click()
                logger.info(f"[{self.account_name}] ✓ 已点击'我的素材'标签")
                await self.random_delay(1, 2)
        except Exception as e:
            logger.warning(f"[{self.account_name}] 点击'我的素材'标签失败: {e}")

        # 3. 选择第一张图片
        logger.info(f"[{self.account_name}] 正在选择第一张图片...")
        try:
            first_image = await page.wait_for_selector(
                ToutiaoSelectors.MATERIAL_FIRST_IMAGE,
                timeout=5000
            )
            if first_image:
                await first_image.click()
                logger.info(f"[{self.account_name}] ✓ 已选择第一张图片")
                await self.random_delay(0.5, 1)
            else:
                logger.warning(f"[{self.account_name}] 未找到素材图片")
                return
        except Exception as e:
            logger.warning(f"[{self.account_name}] 选择图片失败: {e}")
            return

        # 4. 点击确定按钮
        logger.info(f"[{self.account_name}] 正在点击确定按钮...")
        try:
            confirm_btn = await page.wait_for_selector(
                ToutiaoSelectors.MATERIAL_CONFIRM_BTN,
                timeout=3000
            )
            if confirm_btn:
                await confirm_btn.click()
                logger.info(f"[{self.account_name}] ✓ 已点击确定按钮，封面选择完成")
                await self.random_delay(1, 2)
        except Exception as e:
            logger.warning(f"[{self.account_name}] 点击确定按钮失败: {e}")
