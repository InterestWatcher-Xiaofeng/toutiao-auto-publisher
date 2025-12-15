"""
搜狐平台适配器

搜狐号发布流程：
1. 进入内容管理页面: https://mp.sohu.com/mpfe/v4/contentManagement/first/page
2. 点击"发布内容"按钮
3. 输入标题
4. 输入正文（Quill富文本编辑器）
5. 选择封面（从素材库）
6. 点击发布按钮
7. 等待发布成功
"""

import asyncio
import random
from typing import Dict, Any
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.adapters.base_adapter import BaseAdapter
from src.core.logger import get_logger
from src.utils.excel_reader import Article

logger = get_logger()


# 搜狐号页面元素选择器
class SohuSelectors:
    """搜狐号页面元素选择器"""
    # 发布内容按钮
    PUBLISH_CONTENT_BTN = "#menu-ic_publish > div > div > span"

    # 标题输入框
    TITLE_INPUT = "#app > div.add_content-wrap > div > div > div:nth-child(1) > div > div.publish-title > input[type=text]"

    # 正文编辑器（Quill编辑器）
    CONTENT_EDITOR = "#editor > div.ql-editor"

    # 封面上传按钮
    COVER_UPLOAD_BTN = "div.upload-file.mp-upload"

    # 素材库标签 - 使用多种选择器尝试
    MATERIAL_TAB_SELECTORS = [
        # 选中状态的素材库标签
        ".el-dialog__wrapper.select-dialog .dialog-title h3.selected",
        # 未选中状态的素材库按钮（通常是第二个h3）
        ".el-dialog__wrapper.select-dialog .dialog-title h3:nth-child(2)",
        # 包含"素材库"文本的元素
        ".el-dialog__wrapper.select-dialog .dialog-title h3:last-child",
        # 弹窗内的对话框标题区域的h3
        ".select-dialog .dialog-title h3:not(.selected)",
    ]

    # 素材库第一张图片 - 点击容器而非img
    MATERIAL_FIRST_IMAGE_SELECTORS = [
        # 点击整个图片容器
        ".el-dialog__wrapper.select-dialog .library-images > div:nth-child(1)",
        # 点击图片包装器
        ".el-dialog__wrapper.select-dialog .library-images > div:nth-child(1) .image-wrapper",
        # 点击图片本身
        ".el-dialog__wrapper.select-dialog .library-images > div:nth-child(1) img",
        # 备用选择器
        ".library-images > div:first-child",
        ".library-images > div:first-child .image-wrapper",
    ]

    # 素材选择确定按钮
    MATERIAL_CONFIRM_BTN = ".el-dialog__wrapper.select-dialog .bottom-buttons .positive-button"

    # 发布按钮 - 多种选择器
    PUBLISH_BTN_SELECTORS = [
        # 用户提供的完整选择器
        "#app > div.add_content-wrap > div > div > div:nth-child(2) > div.item-btn-wrapper > div > div.bottom-button-outer-absolute > div > ul > li.publish-report-btn.active.positive-button",
        # 简化的类选择器
        "li.publish-report-btn.positive-button",
        "li.publish-report-btn.active",
        ".publish-report-btn.positive-button",
        ".publish-report-btn",
        # 备用选择器
        ".bottom-button-outer-absolute li.positive-button",
        ".item-btn-wrapper .positive-button",
    ]


class SohuAdapter(BaseAdapter):
    """搜狐号适配器"""

    PLATFORM_NAME = "sohu"
    # 搜狐号创作平台
    LOGIN_URL = "https://mp.sohu.com/mpfe/v3/login"
    CONTENT_MANAGE_URL = "https://mp.sohu.com/mpfe/v4/contentManagement/first/page"
    HOME_URL = "https://mp.sohu.com/mpfe/v3/home"
    
    async def check_login_status(self) -> bool:
        """检查登录状态

        注意：搜狐可能需要短信验证，即使有cookie也可能需要二次验证
        需要检测验证页面，避免误判为已登录
        """
        try:
            page = await self.get_page()
            logger.info(f"[{self.account_name}] 正在检查登录状态...")

            # 访问首页
            await page.goto(self.HOME_URL, wait_until='domcontentloaded', timeout=60000)
            await self.random_delay(2, 3)

            # 检查是否被重定向到登录页或验证页
            current_url = page.url.lower()

            # 需要登录或验证的URL关键词
            auth_keywords = ['login', 'verify', 'captcha', 'sms', 'auth', 'passport', 'security']
            for keyword in auth_keywords:
                if keyword in current_url:
                    logger.info(f"[{self.account_name}] 需要登录/验证，当前URL: {current_url}")
                    return False

            # 检查页面是否有验证相关元素（短信验证、图形验证码等）
            try:
                verify_element = await page.query_selector(
                    'input[type="tel"], .verify-code, .sms-code, .captcha, [class*="verify"], [class*="captcha"]'
                )
                if verify_element:
                    logger.info(f"[{self.account_name}] 检测到验证元素，需要完成验证")
                    return False
            except Exception:
                pass

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
    
    async def get_nickname(self) -> str:
        """获取当前登录账号的昵称。

        Returns:
            str: 账号昵称，获取失败返回空字符串
        """
        try:
            page = await self.get_page()

            # 尝试获取用户昵称
            selectors = [
                ".user-name",
                ".nick-name",
                ".author-name",
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

            return ""
        except Exception as e:
            logger.error(f"[{self.account_name}] 获取昵称失败: {e}")
            return ""

    async def wait_for_login(self) -> tuple:
        """等待用户手动登录

        Returns:
            tuple: (success: bool, nickname: str) 登录是否成功以及账号昵称
        """
        try:
            page = await self.get_page()
            logger.info(f"[{self.account_name}] 请在浏览器中手动登录...")

            # 跳转到登录页（延长超时到2分钟，避免验证码场景超时）
            try:
                await page.goto(self.LOGIN_URL, wait_until='domcontentloaded', timeout=120000)
            except Exception as e:
                logger.warning(f"[{self.account_name}] 打开登录页超时，但继续等待登录: {e}")

            # 等待用户登录成功（最多等待5分钟）
            max_wait = 300
            check_interval = 1  # 每1秒检查一次（更快响应取消）
            waited = 0

            # 需要登录或验证的URL关键词
            auth_keywords = ['login', 'verify', 'captcha', 'sms', 'auth', 'passport', 'security']

            while waited < max_wait:
                # 检查取消标志
                if self._cancelled:
                    logger.info(f"[{self.account_name}] 登录等待已取消")
                    return (False, "")

                await asyncio.sleep(check_interval)
                waited += check_interval

                current_url = page.url.lower()

                # 检查URL是否包含任何需要验证的关键词
                needs_auth = any(keyword in current_url for keyword in auth_keywords)

                # 检查页面是否有验证相关元素（短信验证、图形验证码等）
                has_verify_element = False
                try:
                    verify_element = await page.query_selector(
                        'input[type="tel"], .verify-code, .sms-code, .captcha, '
                        '[class*="verify"], [class*="captcha"], [class*="phone"], '
                        'input[placeholder*="验证"], input[placeholder*="手机"]'
                    )
                    has_verify_element = verify_element is not None
                except Exception:
                    pass

                # 只有当URL不包含验证关键词，且页面没有验证元素时，才认为登录成功
                if not needs_auth and not has_verify_element:
                    # 额外检查是否真的到了首页或管理页面
                    if 'home' in current_url or 'content' in current_url or 'mpfe/v' in current_url:
                        logger.info(f"[{self.account_name}] 登录成功！当前URL: {current_url}")
                        await self.save_login_state()

                        # 获取昵称
                        nickname = await self.get_nickname()
                        return (True, nickname)

                if waited % 10 == 0:  # 每10秒打印一次日志
                    logger.info(f"[{self.account_name}] 等待登录中... ({waited}/{max_wait}秒) URL: {current_url}")

            logger.warning(f"[{self.account_name}] 登录超时")
            return (False, "")

        except Exception as e:
            logger.error(f"[{self.account_name}] 等待登录失败: {e}")
            return (False, "")
    
    async def publish_article(self, article: Article) -> Dict[str, Any]:
        """
        发布文章到搜狐号

        完整流程：
        1. 打开内容管理页面
        2. 点击"发布内容"按钮
        3. 输入标题
        4. 输入正文
        5. 选择封面（从素材库）
        6. 点击发布按钮
        7. 等待发布完成
        """
        try:
            page = await self.get_page()
            logger.info(f"[{self.account_name}] 开始发布文章: {article.title[:30]}...")

            # 步骤1: 打开内容管理页面
            logger.info(f"[{self.account_name}] 正在打开内容管理页面...")
            await page.goto(self.CONTENT_MANAGE_URL, wait_until='domcontentloaded', timeout=60000)
            await self.random_delay(2, 3)

            # 步骤2: 点击"发布内容"按钮
            logger.info(f"[{self.account_name}] 正在点击发布内容按钮...")
            try:
                publish_content_btn = await page.wait_for_selector(
                    SohuSelectors.PUBLISH_CONTENT_BTN,
                    timeout=10000
                )
                if publish_content_btn:
                    await publish_content_btn.click()
                    logger.info(f"[{self.account_name}] ✓ 已点击发布内容按钮")
                    await self.random_delay(2, 3)
            except Exception as e:
                logger.error(f"[{self.account_name}] 点击发布内容按钮失败: {e}")
                return {'success': False, 'message': f"点击发布内容按钮失败: {e}"}

            # 步骤3: 输入标题
            logger.info(f"[{self.account_name}] 正在输入标题...")
            try:
                title_input = await page.wait_for_selector(
                    SohuSelectors.TITLE_INPUT,
                    timeout=10000
                )
                if title_input:
                    await title_input.click()
                    await self.random_delay(0.3, 0.5)
                    await title_input.fill(article.title)
                    logger.info(f"[{self.account_name}] ✓ 标题输入成功")
                    await self.random_delay(0.5, 1)
            except Exception as e:
                logger.error(f"[{self.account_name}] 输入标题失败: {e}")
                return {'success': False, 'message': f"输入标题失败: {e}"}

            # 步骤4: 输入正文
            logger.info(f"[{self.account_name}] 正在输入正文...")
            try:
                content_editor = await page.wait_for_selector(
                    SohuSelectors.CONTENT_EDITOR,
                    timeout=10000
                )
                if content_editor:
                    await content_editor.click()
                    await self.random_delay(0.3, 0.5)
                    # 使用键盘输入模拟人工打字
                    await page.keyboard.type(article.content, delay=random.randint(10, 30))
                    logger.info(f"[{self.account_name}] ✓ 正文输入成功")
                    await self.random_delay(1, 2)
            except Exception as e:
                logger.error(f"[{self.account_name}] 输入正文失败: {e}")
                return {'success': False, 'message': f"输入正文失败: {e}"}

            # 步骤5: 选择封面（从素材库）
            logger.info(f"[{self.account_name}] 正在选择封面...")
            try:
                await self._select_cover_from_material(page)
            except Exception as e:
                logger.warning(f"[{self.account_name}] 选择封面失败（继续发布）: {e}")

            # 步骤6: 点击发布按钮
            logger.info(f"[{self.account_name}] 正在点击发布按钮...")
            publish_clicked = False

            for selector in SohuSelectors.PUBLISH_BTN_SELECTORS:
                try:
                    publish_btn = await page.wait_for_selector(selector, timeout=3000)
                    if publish_btn:
                        # 滚动到按钮可见位置
                        await publish_btn.scroll_into_view_if_needed()
                        await self.random_delay(0.3, 0.5)
                        await publish_btn.click()
                        logger.info(f"[{self.account_name}] ✓ 已点击发布按钮 (选择器: {selector})")
                        publish_clicked = True
                        await self.random_delay(2, 3)
                        break
                except Exception as e:
                    logger.debug(f"[{self.account_name}] 发布按钮选择器 {selector} 失败: {e}")
                    continue

            # 如果常规点击失败，尝试文本定位
            if not publish_clicked:
                try:
                    await page.get_by_text("发布", exact=True).click()
                    logger.info(f"[{self.account_name}] ✓ 已点击发布按钮 (文本定位)")
                    publish_clicked = True
                    await self.random_delay(2, 3)
                except Exception as e:
                    logger.debug(f"[{self.account_name}] 文本定位发布按钮失败: {e}")

            # 尝试 JavaScript 点击
            if not publish_clicked:
                try:
                    result = await page.evaluate("""
                        () => {
                            const btns = document.querySelectorAll('.publish-report-btn, .positive-button');
                            for (const btn of btns) {
                                const text = btn.innerText || btn.textContent;
                                if (text && text.includes('发布')) {
                                    btn.click();
                                    return {success: true, text: text};
                                }
                            }
                            return {success: false};
                        }
                    """)
                    if result and result.get('success'):
                        logger.info(f"[{self.account_name}] ✓ 已通过JavaScript点击发布按钮")
                        publish_clicked = True
                        await self.random_delay(2, 3)
                except Exception as e:
                    logger.warning(f"[{self.account_name}] JavaScript点击发布按钮失败: {e}")

            if not publish_clicked:
                logger.error(f"[{self.account_name}] 未能点击发布按钮")
                return {'success': False, 'message': "未能点击发布按钮"}

            # 步骤7: 等待发布完成
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

    async def _select_cover_from_material(self, page: Page):
        """从素材库选择封面图片"""
        # 1. 点击封面上传按钮
        logger.info(f"[{self.account_name}] 正在点击封面上传按钮...")
        try:
            cover_btn = await page.wait_for_selector(
                SohuSelectors.COVER_UPLOAD_BTN,
                timeout=5000
            )
            if cover_btn:
                await cover_btn.click()
                logger.info(f"[{self.account_name}] ✓ 已点击封面上传按钮")
                await self.random_delay(1, 2)
            else:
                logger.warning(f"[{self.account_name}] 未找到封面上传按钮")
                return
        except Exception as e:
            logger.warning(f"[{self.account_name}] 点击封面上传按钮失败: {e}")
            return

        # 2. 等待弹窗出现
        logger.info(f"[{self.account_name}] 等待素材选择弹窗...")
        await self.random_delay(2, 3)

        # 3. 点击"素材库"标签 - 使用文本定位
        logger.info(f"[{self.account_name}] 正在点击'素材库'标签...")
        material_tab_clicked = False

        # 方法1: 使用 Playwright 的文本定位器直接点击
        try:
            await page.get_by_text("素材库", exact=True).click()
            logger.info(f"[{self.account_name}] ✓ 已点击'素材库'标签 (使用文本定位)")
            material_tab_clicked = True
            await self.random_delay(2, 3)
        except Exception as e:
            logger.debug(f"[{self.account_name}] 文本定位失败: {e}")

        # 方法2: 如果方法1失败，使用 locator 点击
        if not material_tab_clicked:
            try:
                await page.locator("text=素材库").click()
                logger.info(f"[{self.account_name}] ✓ 已点击'素材库'标签 (使用locator)")
                material_tab_clicked = True
                await self.random_delay(2, 3)
            except Exception as e:
                logger.debug(f"[{self.account_name}] locator点击失败: {e}")

        # 方法3: 遍历所有标签查找
        if not material_tab_clicked:
            try:
                # 查找弹窗中的所有标签文字
                tabs = await page.query_selector_all(".el-dialog h3, .el-dialog span, .dialog-title h3, .dialog-title span")
                for tab in tabs:
                    try:
                        text = await tab.inner_text()
                        if "素材库" in text or text.strip() == "素材库":
                            await tab.click()
                            logger.info(f"[{self.account_name}] ✓ 已点击'素材库'标签 (通过遍历)")
                            material_tab_clicked = True
                            await self.random_delay(2, 3)
                            break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"[{self.account_name}] 遍历标签失败: {e}")

        if not material_tab_clicked:
            logger.warning(f"[{self.account_name}] 未能点击素材库标签，尝试继续...")

        # 4. 等待素材库图片加载
        await self.random_delay(2, 3)

        # 5. 选择第一张图片 - 尝试多种选择器
        logger.info(f"[{self.account_name}] 正在选择第一张图片...")
        image_selected = False

        for selector in SohuSelectors.MATERIAL_FIRST_IMAGE_SELECTORS:
            try:
                first_image = await page.wait_for_selector(selector, timeout=3000)
                if first_image:
                    # 尝试先滚动到元素可见位置
                    await first_image.scroll_into_view_if_needed()
                    await self.random_delay(0.3, 0.5)
                    # 点击选中
                    await first_image.click()
                    logger.info(f"[{self.account_name}] ✓ 已点击图片 (选择器: {selector})")
                    image_selected = True
                    await self.random_delay(1, 2)
                    break
            except Exception as e:
                logger.debug(f"[{self.account_name}] 选择器 {selector} 失败: {e}")
                continue

        # 如果常规点击不行，尝试JavaScript点击
        if not image_selected:
            try:
                # 获取所有素材库图片容器
                result = await page.evaluate("""
                    () => {
                        // 找到素材库中的图片项
                        const items = document.querySelectorAll('.library-images > div, .image-list > div, .el-dialog .image-item');
                        if (items.length > 0) {
                            // 点击第一个
                            items[0].click();
                            return {success: true, count: items.length};
                        }
                        return {success: false, count: 0};
                    }
                """)
                if result and result.get('success'):
                    logger.info(f"[{self.account_name}] ✓ 通过JavaScript点击了图片 (共{result.get('count')}张)")
                    image_selected = True
                    await self.random_delay(1, 2)
            except Exception as e:
                logger.warning(f"[{self.account_name}] JavaScript点击失败: {e}")

        if image_selected:
            logger.info(f"[{self.account_name}] ✓ 已选择第一张图片")
            await self.random_delay(0.5, 1)
        else:
            logger.warning(f"[{self.account_name}] 未找到素材图片")
            return

        # 6. 点击确定按钮
        logger.info(f"[{self.account_name}] 正在点击确定按钮...")
        try:
            confirm_btn = await page.wait_for_selector(
                SohuSelectors.MATERIAL_CONFIRM_BTN,
                timeout=5000
            )
            if confirm_btn:
                await confirm_btn.click()
                logger.info(f"[{self.account_name}] ✓ 已点击确定按钮，封面选择完成")
                await self.random_delay(1, 2)
        except Exception as e:
            logger.warning(f"[{self.account_name}] 点击确定按钮失败: {e}")

