"""百家号平台适配器

实现百家号文章发布流程：
1. 打开发布页面
2. 填写标题
3. 填写正文
4. 选择封面（单图 + 本地上传）
5. 点击发布
"""

import asyncio
from typing import Dict, Any

from src.adapters.base_adapter import BaseAdapter
from src.core.logger import get_logger
from src.utils.excel_reader import Article


logger = get_logger()


# 百家号页面元素选择器
class BaijiahaoSelectors:
    """百家号页面元素选择器"""
    # 发布作品按钮
    PUBLISH_WORK_BTN = "#home-publish-btn > div._4f4cb3a3b81b55a5-expandContent"
    
    # 标题输入框
    TITLE_INPUT = "#newsTextArea > div > div > div > div > div > div > div.client_pages_edit_components_titleInput > div > div.input-box > div._9ddb7e475b559749-editor._377c94a778c072b3-editor > p"
    
    # 正文编辑器
    CONTENT_EDITOR = "body"
    
    # 单图选项框 (2025-12-23更新)
    SINGLE_IMAGE_RADIO = "#bjhNewsCover > div > div > div.cheetah-col.cheetah-form-item-control.cheetah-col-xs-24.cheetah-col-sm-20.css-1o1cgpv > div > div > div[class*='list'] > div > div > div > div > div"
    SINGLE_IMAGE_SELECTORS = [
        "#bjhNewsCover > div > div > div.cheetah-col.cheetah-form-item-control.cheetah-col-xs-24.cheetah-col-sm-20.css-1o1cgpv > div > div > div[class*='list'] > div > div > div > div > div",
        "label:has-text('单图')",
        "span:has-text('单图')",
        "#bjhNewsCover .cover-radio-group label:nth-child(2)",
    ]

    # 图片选择框（点击后打开图片选择弹窗）
    IMAGE_SELECT_BOX = "#bjhNewsCover > div > div.cheetah-row.cheetah-form-item-row.css-1o1cgpv > div.cheetah-col.cheetah-form-item-control.cheetah-col-xs-24.cheetah-col-sm-20.css-1o1cgpv > div.cheetah-form-item-control-input > div > div > div.cover-list.cover-list-one > div > div.wrap-scale-DraggableTags > div > div > div.DraggableTags-tag-drag > div > div"
    IMAGE_SELECT_BOX_SELECTORS = [
        "#bjhNewsCover .cover-list-one .DraggableTags-tag-drag",
        "#bjhNewsCover .cover-list .wrap-scale-DraggableTags",
        ".cover-list-one div[class*='upload']",
        "#bjhNewsCover [class*='add']",
    ]

    # 免费正版图库标签 (2025-12-23更新)
    AUTH_LIB_TAB = "#rc-tabs-1-tab-authLib"
    AUTH_LIB_TAB_SELECTORS = [
        "#rc-tabs-1-tab-authLib",
        "#rc-tabs-2-tab-authLib",
        "#rc-tabs-0-tab-authLib",
        "[role='tab']:has-text('免费正版')",
    ]

    # 免费正版图库搜索框 (2025-12-23更新)
    AUTH_LIB_SEARCH = "#rc-tabs-1-panel-authLib input"
    AUTH_LIB_SEARCH_SELECTORS = [
        "#rc-tabs-1-panel-authLib input",
        "#rc-tabs-2-panel-authLib input",
        "#rc-tabs-0-panel-authLib input",
        "[class*='authLib'] input",
    ]

    # 免费正版图库图片选择 - 点击图片本身（img），模拟真人点击
    AUTH_LIB_IMAGE = "#rc-tabs-1-panel-authLib .pubu-content > div:nth-child(5) > img"
    AUTH_LIB_IMAGE_SELECTORS = [
        "#rc-tabs-1-panel-authLib .pubu-content > div:nth-child(5) > img",
        "#rc-tabs-1-panel-authLib .pubu-content > div:nth-child(4) > img",
        "#rc-tabs-1-panel-authLib .pubu-content > div:nth-child(3) > img",
        "#rc-tabs-2-panel-authLib .pubu-content > div:nth-child(5) > img",
        "#rc-tabs-2-panel-authLib .pubu-content > div:nth-child(4) > img",
        "[class*='authLib'] .pubu-content > div > img",
        ".pubu-content > div:nth-child(5) > img",
    ]

    # 确认按钮 (2025-01-01更新)
    CONFIRM_BTN = "[class*='bottom'] button.cheetah-btn-primary"
    CONFIRM_BTN_SELECTORS = [
        # 新版选择器
        "#rc-tabs-1-panel-authLib [class*='bottom'] button.cheetah-btn-primary",
        "#rc-tabs-2-panel-authLib [class*='bottom'] button.cheetah-btn-primary",
        "[class*='authLib'] [class*='bottom'] button.cheetah-btn-primary",
        "[class*='bottom'] button.cheetah-btn-primary span",
        # 备用
        ".cheetah-btn-primary:has-text('确定')",
        "button:has-text('确定')",
    ]

    # 发布按钮 (2025-01-01更新)
    PUBLISH_BTN = "#root .op-list-right > div:nth-child(4) > button > span"
    PUBLISH_BTN_SELECTORS = [
        "#root .op-list-right > div:nth-child(4) > button > span",
        "#root .op-list-right > div:nth-child(4) > button",
        ".op-list-right button:has-text('发布')",
        "button:has-text('发布')",
    ]


class BaijiahaoAdapter(BaseAdapter):
    """百家号平台适配器"""

    PLATFORM_NAME = "baijiahao"
    LOGIN_URL = "https://baijiahao.baidu.com/builder/rc/login"
    PUBLISH_URL = "https://baijiahao.baidu.com/builder/rc/edit?type=news"
    HOME_URL = "https://baijiahao.baidu.com/builder/rc/noticemessage/notice_system"

    async def check_login_status(self) -> bool:
        """检查登录状态"""
        page = await self.get_page()
        logger.info(f"[{self.account_name}] 正在检查登录状态（百家号）...")

        current_url = page.url or ""
        logger.info(f"[{self.account_name}] 当前URL: {current_url}")

        if not current_url or current_url.startswith("about:blank"):
            logger.info(f"[{self.account_name}] 当前为空白页，视为【未登录】")
            return False

        if "login" in current_url or "passport" in current_url:
            logger.info(f"[{self.account_name}] 判断为【未登录】（命中 login/passport）")
            return False

        logger.info(f"[{self.account_name}] 判断为【已登录】")
        return True

    async def get_nickname(self) -> str:
        """获取当前登录账号的昵称"""
        try:
            page = await self.get_page()
            await page.goto(self.HOME_URL, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)

            # 尝试获取昵称的选择器
            selectors = [
                ".author-name",
                ".user-name",
                ".account-name",
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

            logger.warning(f"[{self.account_name}] 无法获取昵称")
            return ""
        except Exception as e:
            logger.error(f"[{self.account_name}] 获取昵称失败: {e}")
            return ""

    async def wait_for_login(self) -> tuple:
        """等待用户手动登录

        Returns:
            tuple: (success: bool, nickname: str)
        """
        page = await self.get_page()
        logger.info(f"[{self.account_name}] 请在弹出的浏览器中手动登录百家号...")

        try:
            await page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.error(f"[{self.account_name}] 打开登录页失败: {e}")
            return (False, "")

        # 轮询检测登录状态，最长5分钟
        max_wait = 300
        interval = 2
        waited = 0

        while waited < max_wait:
            if self._cancelled:
                logger.info(f"[{self.account_name}] 登录等待已取消")
                return (False, "")

            await asyncio.sleep(interval)
            waited += interval

            current_url = page.url or ""

            # 检测URL是否已离开登录页
            if "login" not in current_url and "passport" not in current_url and current_url != "about:blank":
                logger.info(f"[{self.account_name}] URL已变化，尝试验证登录状态...")

                # 主动导航到后台首页验证登录
                try:
                    await page.goto(self.HOME_URL, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)

                    # 检查是否被重定向回登录页
                    verify_url = page.url or ""
                    if "login" not in verify_url and "passport" not in verify_url:
                        logger.info(f"[{self.account_name}] ✅ 登录验证成功，当前URL: {verify_url}")

                        # 保存登录状态
                        try:
                            await self.save_login_state()
                        except Exception:
                            pass

                        nickname = await self.get_nickname()
                        return (True, nickname)
                    else:
                        logger.debug(f"[{self.account_name}] 被重定向回登录页，继续等待...")
                except Exception as e:
                    logger.debug(f"[{self.account_name}] 验证登录时出错: {e}")

            if waited % 10 == 0:
                logger.debug(f"[{self.account_name}] 等待登录中... ({waited}/{max_wait} 秒)")

        logger.warning(f"[{self.account_name}] 登录等待超时")
        return (False, "")

    async def _close_tour_popups(self, page):
        """关闭新功能引导弹窗"""
        max_attempts = 5
        for attempt in range(max_attempts):
            closed_any = False

            close_selectors = [
                ".cheetah-tour-close",
                ".cheetah-tour-skip",
                "button:has-text('跳过')",
                "button:has-text('知道了')",
                "button:has-text('我知道了')",
                "button:has-text('下一步')",
                "button:has-text('完成')",
                ".tour-close",
                "[aria-label='Close']",
                ".cheetah-modal-close",
                ".ant-modal-close",
            ]

            for selector in close_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=1000)
                    if element:
                        await element.click()
                        logger.debug(f"[{self.account_name}] 关闭弹窗: {selector}")
                        await asyncio.sleep(0.5)
                        closed_any = True
                        break
                except Exception:
                    continue

            if not closed_any:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)

            try:
                still_has_tour = await page.query_selector(".cheetah-tour, .cheetah-modal, .ant-modal")
                if not still_has_tour:
                    break
            except:
                break

            await asyncio.sleep(0.5)

        await page.keyboard.press("Escape")
        await asyncio.sleep(1)

    async def publish_article(self, article: Article) -> Dict[str, Any]:
        """发布文章到百家号

        Args:
            article: 文章对象

        Returns:
            发布结果 {'success': bool, 'message': str}
        """
        if self._cancelled:
            return {"success": False, "message": "任务已取消"}

        page = await self.get_page()
        logger.info(f"[{self.account_name}] 开始发布文章: {article.title[:30]}...")

        try:
            # 步骤1: 进入后台首页
            logger.info(f"[{self.account_name}] 步骤1: 进入后台首页")
            await page.goto(self.HOME_URL, wait_until="domcontentloaded", timeout=30000)
            await self.random_delay(2, 3)

            # 步骤2: 点击"发布作品"按钮
            logger.info(f"[{self.account_name}] 步骤2: 点击发布作品按钮")
            await page.click(BaijiahaoSelectors.PUBLISH_WORK_BTN)
            await self.random_delay(2, 3)

            # 步骤2.5: 关闭新功能引导弹窗
            logger.info(f"[{self.account_name}] 步骤2.5: 关闭引导弹窗")
            await self._close_tour_popups(page)

            # 步骤3: 填写标题（使用fill方法直接复制）
            logger.info(f"[{self.account_name}] 步骤3: 填写标题")
            await asyncio.sleep(2)
            title_selectors = [
                BaijiahaoSelectors.TITLE_INPUT,
                "textarea",
                "[placeholder*='标题']",
            ]
            title_filled = False
            for selector in title_selectors:
                try:
                    await page.fill(selector, article.title)
                    logger.info(f"[{self.account_name}] ✓ 标题填写完成")
                    title_filled = True
                    break
                except Exception:
                    continue
            if not title_filled:
                logger.warning(f"[{self.account_name}] 标题填写失败")
            await self.random_delay(2, 3)

            # 步骤4: 填写正文（正文在iframe里，使用UEditor）
            logger.info(f"[{self.account_name}] 步骤4: 填写正文")
            try:
                ueditor_frame = page.frame_locator("#ueditor_0")
                body_element = ueditor_frame.locator("body")
                await body_element.click()
                await asyncio.sleep(0.5)
                await body_element.fill(article.content)
                logger.info(f"[{self.account_name}] ✓ 正文填写完成")
            except Exception as e:
                logger.warning(f"[{self.account_name}] 正文填写失败: {e}")
            await self.random_delay(2, 3)

            # 步骤5: 点击"单图"选项框 - 使用多选择器策略
            logger.info(f"[{self.account_name}] 步骤5: 点击单图选项")
            try:
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(1)

                # 多选择器策略
                single_image_clicked = False
                for selector in BaijiahaoSelectors.SINGLE_IMAGE_SELECTORS:
                    try:
                        element = await page.wait_for_selector(selector, timeout=2000)
                        if element:
                            await element.click()
                            logger.info(f"[{self.account_name}] ✓ 单图选项已选择 (选择器: {selector[:50]}...)")
                            single_image_clicked = True
                            break
                    except Exception:
                        continue

                if not single_image_clicked:
                    # 最后尝试使用主选择器强制点击
                    await page.click(BaijiahaoSelectors.SINGLE_IMAGE_RADIO, force=True)
                    logger.info(f"[{self.account_name}] ✓ 单图选项已选择 (强制点击)")

                await self.random_delay(1, 2)
            except Exception as e:
                logger.warning(f"[{self.account_name}] 点击单图选项失败: {e}")

            # 步骤6: 点击"免费正版图库"标签（跳过图片选择框步骤）
            logger.info(f"[{self.account_name}] 步骤6: 点击免费正版图库标签")
            await asyncio.sleep(2)
            auth_lib_clicked = False
            for selector in BaijiahaoSelectors.AUTH_LIB_TAB_SELECTORS:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        await element.click()
                        logger.info(f"[{self.account_name}] ✓ 免费正版图库标签已点击")
                        auth_lib_clicked = True
                        break
                except Exception:
                    continue
            if not auth_lib_clicked:
                logger.warning(f"[{self.account_name}] 免费正版图库标签点击失败")
            await self.random_delay(1, 2)

            # 步骤7: 搜索"渡鸦"
            logger.info(f"[{self.account_name}] 步骤7: 搜索图片")
            search_done = False
            for selector in BaijiahaoSelectors.AUTH_LIB_SEARCH_SELECTORS:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        await element.click()
                        await asyncio.sleep(0.5)
                        await page.fill(selector, "渡鸦")
                        await asyncio.sleep(0.5)
                        await page.keyboard.press("Enter")
                        logger.info(f"[{self.account_name}] ✓ 搜索完成")
                        search_done = True
                        break
                except Exception:
                    continue
            if not search_done:
                logger.warning(f"[{self.account_name}] 搜索操作失败")
            await self.random_delay(2, 3)

            # 步骤8: 选择图片（点击图片本身，模拟真人点击）
            logger.info(f"[{self.account_name}] 步骤8: 选择图片")
            image_selected = False
            for selector in BaijiahaoSelectors.AUTH_LIB_IMAGE_SELECTORS:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        # 使用 force=True 确保点击成功
                        await element.click(force=True)
                        logger.info(f"[{self.account_name}] ✓ 图片已选择")
                        image_selected = True
                        break
                except Exception:
                    continue
            if not image_selected:
                logger.warning(f"[{self.account_name}] 图片选择失败")
            await self.random_delay(1, 2)

            # 步骤9: 点击确认按钮
            logger.info(f"[{self.account_name}] 步骤9: 点击确认按钮")
            confirm_clicked = False
            for selector in BaijiahaoSelectors.CONFIRM_BTN_SELECTORS:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        await element.click()
                        logger.info(f"[{self.account_name}] ✓ 确认按钮已点击")
                        confirm_clicked = True
                        break
                except Exception:
                    continue
            if not confirm_clicked:
                logger.warning(f"[{self.account_name}] 确认按钮点击失败")

            # 等待10秒确保页面加载完成
            await asyncio.sleep(10)

            # 步骤10: 点击发布按钮
            logger.info(f"[{self.account_name}] 步骤10: 点击发布按钮")
            publish_clicked = False
            for selector in BaijiahaoSelectors.PUBLISH_BTN_SELECTORS:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        await element.click()
                        logger.info(f"[{self.account_name}] ✓ 发布按钮已点击")
                        publish_clicked = True
                        break
                except Exception:
                    continue
            if not publish_clicked:
                logger.warning(f"[{self.account_name}] 发布按钮点击失败")
            await self.random_delay(3, 5)

            logger.info(f"[{self.account_name}] ✅ 文章发布成功: {article.title[:30]}")
            return {"success": True, "message": "发布成功"}

        except Exception as e:
            logger.error(f"[{self.account_name}] ❌ 发布失败: {e}")
            return {"success": False, "message": str(e)}

