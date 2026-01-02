"""测试百家号发布流程"""

import asyncio
import sys
sys.path.insert(0, '.')

from src.browser.browser_manager import browser_manager
from src.adapters.baijiahao_adapter import BaijiahaoAdapter, BaijiahaoSelectors
from src.utils.excel_reader import ExcelReader, Article


async def debug_find_content_editor():
    """调试：分析页面结构，找到正确的正文编辑器"""
    print("=" * 50)
    print("调试：分析正文编辑器位置")
    print("=" * 50)

    adapter = BaijiahaoAdapter(
        account_id="baijiahao_1",
        profile_dir="baijiahao_account1",
        account_name="百家号测试"
    )

    try:
        page = await adapter.get_page()

        # 进入发布页面
        print("\n进入发布页面...")
        await page.goto("https://baijiahao.baidu.com/builder/rc/edit?type=news", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # 关闭引导弹窗
        try:
            close_btn = await page.wait_for_selector(".cheetah-tour-close", timeout=3000)
            if close_btn:
                await close_btn.click()
                await asyncio.sleep(1)
        except:
            pass
        await page.keyboard.press("Escape")
        await asyncio.sleep(1)

        # 分析页面上所有 contenteditable 元素
        print("\n分析页面上的 contenteditable 元素...")

        result = await page.evaluate("""
            () => {
                const editables = document.querySelectorAll('[contenteditable="true"]');
                const info = [];
                editables.forEach((el, i) => {
                    const rect = el.getBoundingClientRect();
                    info.push({
                        index: i,
                        tagName: el.tagName,
                        className: el.className.substring(0, 100),
                        id: el.id,
                        width: rect.width,
                        height: rect.height,
                        top: rect.top,
                        text: el.innerText.substring(0, 50)
                    });
                });
                return info;
            }
        """)

        print(f"\n找到 {len(result)} 个 contenteditable 元素:")
        for item in result:
            print(f"  [{item['index']}] {item['tagName']} - 类名: {item['className'][:50]}")
            print(f"      尺寸: {item['width']:.0f}x{item['height']:.0f}, 位置: top={item['top']:.0f}")
            print(f"      文本: {item['text'][:30]}")

        # 分析 iframe
        print("\n分析页面上的 iframe...")
        iframes = await page.query_selector_all("iframe")
        print(f"找到 {len(iframes)} 个 iframe")

        # 尝试找到正文编辑器的具体选择器
        print("\n尝试各种正文选择器...")
        selectors_to_test = [
            "#newsTextArea [contenteditable='true']",
            ".editor-container [contenteditable='true']",
            ".news-content-editor [contenteditable='true']",
            ".bjh-editor [contenteditable='true']",
            "[class*='content'] [contenteditable='true']",
            "[class*='editor'] [contenteditable='true']",
            ".ProseMirror",
            "#ueditor_0",
            ".edui-body-container",
        ]

        for selector in selectors_to_test:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    print(f"  ✅ {selector} - 找到 {len(elements)} 个元素")
                    for i, el in enumerate(elements):
                        box = await el.bounding_box()
                        if box:
                            print(f"      [{i}] 尺寸: {box['width']:.0f}x{box['height']:.0f}")
            except Exception as e:
                print(f"  ❌ {selector} - 错误: {str(e)[:30]}")

        print("\n" + "=" * 50)
        print("浏览器保持打开，请手动检查页面结构...")
        print("按 Ctrl+C 退出")
        print("=" * 50)

        while True:
            await asyncio.sleep(10)

    except Exception as e:
        print(f"调试出错: {e}")
        import traceback
        traceback.print_exc()


async def publish_single_article(adapter, page, article, article_index, total_articles):
    """发布单篇文章"""
    print(f"\n{'=' * 50}")
    print(f"正在发布第 {article_index + 1}/{total_articles} 篇文章")
    print(f"标题: {article.title[:40]}...")
    print(f"{'=' * 50}")

    # 步骤1: 进入后台首页
    print("\n[步骤1] 进入后台首页...")
    await page.goto(adapter.HOME_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    print(f"当前URL: {page.url}")

    # 步骤2: 点击发布作品按钮
    print("\n[步骤2] 点击发布作品按钮...")
    await page.click(BaijiahaoSelectors.PUBLISH_WORK_BTN)
    await asyncio.sleep(3)
    print(f"点击后URL: {page.url}")

    # 步骤2.5: 关闭新功能引导弹窗（如果存在）- 多次尝试
    print("\n[步骤2.5] 检查并关闭新功能引导弹窗...")

    # 多次尝试关闭弹窗（可能有多个引导步骤）
    max_attempts = 5
    for attempt in range(max_attempts):
        closed_any = False

        # 尝试多种关闭方式
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
            "svg[class*='close']",
        ]

        for selector in close_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=1000)
                if element:
                    await element.click()
                    print(f"  ✅ 关闭弹窗成功[{attempt+1}]: {selector}")
                    await asyncio.sleep(0.5)
                    closed_any = True
                    break
            except Exception:
                continue

        # 如果没找到关闭按钮，尝试按ESC键
        if not closed_any:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

        # 检查是否还有弹窗
        try:
            still_has_tour = await page.query_selector(".cheetah-tour, .cheetah-modal, .ant-modal")
            if not still_has_tour:
                print(f"  ✅ 所有弹窗已关闭（尝试{attempt+1}次）")
                break
        except:
            break

        await asyncio.sleep(0.5)

    # 最后再按一次ESC确保
    await page.keyboard.press("Escape")
    await asyncio.sleep(1)
    print("✅ 引导弹窗处理完成")

    # 步骤3: 填写标题（使用fill方法直接复制）
    print("\n[步骤3] 填写标题...")
    await asyncio.sleep(2)  # 步骤间隔
    try:
        # 尝试多个可能的标题选择器
        title_selectors = [
            BaijiahaoSelectors.TITLE_INPUT,
            "textarea",
            "[placeholder*='标题']",
            ".title-input textarea",
        ]

        title_filled = False
        for selector in title_selectors:
            try:
                await page.fill(selector, article.title)
                print(f"✅ 标题已填写: {article.title[:30]}... (选择器: {selector[:30]})")
                title_filled = True
                break
            except Exception as e:
                print(f"⚠️ 标题选择器失败: {selector[:30]}... - {str(e)[:50]}")
                continue

        if not title_filled:
            print("❌ 所有标题选择器都失败了")
    except Exception as e:
        print(f"❌ 填写标题失败: {e}")

    await asyncio.sleep(3)  # 步骤间隔

    # 步骤4: 填写正文（正文在iframe里，使用UEditor）
    print("\n[步骤4] 填写正文（iframe内的UEditor）...")
    try:
        # 找到UEditor的iframe
        ueditor_frame = page.frame_locator("#ueditor_0")

        # 在iframe内找到body并填写内容
        body_element = ueditor_frame.locator("body")
        await body_element.click()
        await asyncio.sleep(0.5)

        # 清空现有内容并输入新内容
        await body_element.fill(article.content)
        print(f"✅ 正文已填写: {article.content[:50]}...")
    except Exception as e:
        print(f"⚠️ iframe方式失败: {e}")

        # 备用方案：直接获取iframe并操作
        try:
            print("尝试备用方案...")
            frames = page.frames
            print(f"页面共有 {len(frames)} 个frame")

            for i, frame in enumerate(frames):
                frame_url = frame.url
                print(f"  Frame[{i}]: {frame_url[:50] if frame_url else 'blank'}")

                # 尝试在每个frame中找body
                try:
                    body = await frame.query_selector("body.view")
                    if body:
                        print(f"  ✅ 在Frame[{i}]找到body.view")
                        await body.click()
                        await asyncio.sleep(0.5)
                        await frame.fill("body", article.content)
                        print(f"✅ 正文已填写（备用方案）")
                        break
                except:
                    continue
        except Exception as e2:
            print(f"❌ 备用方案也失败: {e2}")

    await asyncio.sleep(3)  # 步骤间隔

    # 步骤5: 测试封面选项 - 使用多选择器策略
    print("\n[步骤5] 测试封面选项（单图）...")
    try:
        # 滚动到封面区域
        await page.evaluate("window.scrollBy(0, 500)")
        await asyncio.sleep(1)

        # 多选择器策略
        single_image_clicked = False
        for selector in BaijiahaoSelectors.SINGLE_IMAGE_SELECTORS:
            try:
                element = await page.wait_for_selector(selector, timeout=2000)
                if element:
                    await element.click()
                    print(f"✅ 点击单图选项成功: {selector[:50]}")
                    single_image_clicked = True
                    break
            except Exception:
                print(f"  ⚠️ 选择器失败: {selector[:50]}")
                continue

        if not single_image_clicked:
            # 最后尝试使用主选择器强制点击
            await page.click(BaijiahaoSelectors.SINGLE_IMAGE_RADIO, force=True)
            print("✅ 点击单图选项成功（强制点击）")

        await asyncio.sleep(2)
    except Exception as e:
        print(f"⚠️ 封面选项测试失败: {e}")

    # 步骤6: 点击"免费正版图库"标签（跳过图片选择框）
    print("\n[步骤6] 点击免费正版图库标签...")
    await asyncio.sleep(2)
    clicked = False
    for selector in BaijiahaoSelectors.AUTH_LIB_TAB_SELECTORS:
        try:
            element = await page.wait_for_selector(selector, timeout=2000)
            if element:
                await element.click()
                print(f"✅ 点击免费正版图库标签成功: {selector[:50]}")
                clicked = True
                break
        except Exception:
            print(f"  ⚠️ 选择器失败: {selector[:50]}")
    if not clicked:
        print("❌ 所有免费正版图库标签选择器都失败")
    await asyncio.sleep(2)

    # 步骤7: 搜索"渡鸦"
    print("\n[步骤7] 搜索渡鸦...")
    searched = False
    for selector in BaijiahaoSelectors.AUTH_LIB_SEARCH_SELECTORS:
        try:
            element = await page.wait_for_selector(selector, timeout=2000)
            if element:
                await element.click()
                await asyncio.sleep(0.5)
                await page.fill(selector, "渡鸦")
                print(f"✅ 输入搜索词成功: {selector[:50]}")
                searched = True
                break
        except Exception:
            print(f"  ⚠️ 选择器失败: {selector[:50]}")
    if searched:
        await asyncio.sleep(0.5)
        await page.keyboard.press("Enter")
        print("✅ 按回车搜索")
    else:
        print("❌ 搜索输入失败")
    await asyncio.sleep(3)

    # 步骤8: 选择图片（点击图片本身，模拟真人）
    print("\n[步骤8] 选择图片（点击图片）...")
    clicked = False
    for selector in BaijiahaoSelectors.AUTH_LIB_IMAGE_SELECTORS:
        try:
            element = await page.wait_for_selector(selector, timeout=2000)
            if element:
                # 使用 force=True 确保点击成功
                await element.click(force=True)
                print(f"✅ 选择图片成功: {selector[:50]}")
                clicked = True
                break
        except Exception:
            print(f"  ⚠️ 选择器失败: {selector[:50]}")
    if not clicked:
        print("❌ 所有图片选择器都失败")
    await asyncio.sleep(2)

    # 步骤9: 点击确认按钮
    print("\n[步骤9] 点击确认按钮...")
    clicked = False
    for selector in BaijiahaoSelectors.CONFIRM_BTN_SELECTORS:
        try:
            element = await page.wait_for_selector(selector, timeout=3000)
            if element:
                await element.click()
                print(f"✅ 点击确认按钮成功")
                clicked = True
                break
        except Exception:
            print(f"  ⚠️ 选择器失败: {selector[:50]}")
    if not clicked:
        print("❌ 所有确认按钮选择器都失败")
    await asyncio.sleep(10)

    # 步骤10: 点击发布按钮
    print("\n[步骤10] 点击发布按钮（等待10秒后）...")
    clicked = False
    for selector in BaijiahaoSelectors.PUBLISH_BTN_SELECTORS:
        try:
            element = await page.wait_for_selector(selector, timeout=3000)
            if element:
                await element.click()
                print(f"✅ 点击发布按钮成功")
                clicked = True
                break
        except Exception:
            print(f"  ⚠️ 选择器失败: {selector[:50]}")
    if not clicked:
        print("❌ 所有发布按钮选择器都失败")

    await asyncio.sleep(5)
    print(f"\n✅ 第 {article_index + 1}/{total_articles} 篇文章发布完成!")


async def test_publish():
    """测试发布流程 - 发布所有文章"""
    print("=" * 50)
    print("百家号发布流程 - 发布所有文章")
    print("=" * 50)

    # 读取CSV文件
    csv_path = r"C:\Users\Yu feng\Desktop\流水线\文章_拆分结果.csv"
    reader = ExcelReader()
    if not reader.load(csv_path):
        print(f"❌ 无法加载CSV文件: {csv_path}")
        return

    print(f"✅ 加载了 {len(reader.articles)} 篇文章")

    # 创建适配器
    adapter = BaijiahaoAdapter(
        account_id="baijiahao_1",
        profile_dir="baijiahao_account1",
        account_name="百家号测试"
    )

    try:
        # 获取页面
        page = await adapter.get_page()

        # 循环发布所有文章
        total_articles = len(reader.articles)
        for i, article in enumerate(reader.articles):
            await publish_single_article(adapter, page, article, i, total_articles)

            # 如果不是最后一篇，等待一段时间再发布下一篇
            if i < total_articles - 1:
                print(f"\n⏳ 等待5秒后发布下一篇...")
                await asyncio.sleep(5)

        print("\n" + "=" * 50)
        print(f"🎉 所有 {total_articles} 篇文章发布完成!")
        print("=" * 50)

    except Exception as e:
        print(f"测试出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 运行发布测试
    asyncio.run(test_publish())

