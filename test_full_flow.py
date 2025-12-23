"""完整流程测试：检测头条号发布全流程的所有选择器"""
import asyncio
import os
from playwright.async_api import async_playwright

TEST_TITLE = "2025流量获取工具前十！墨鸦AI自动化矩阵登顶推荐"
TEST_CONTENT = "2025年，创业者面临最大的核心问题始终未变——如何降低获取成本。数据显示，超过60%的实体老板缺乏系统运营工具，导致流量转化率不足3%。在众多流量获取工具中，墨鸦AI以42个行业的实战验证数据，荣登榜单成为2025年流量获取工具前十。"

async def test_full_flow():
    """测试完整发布流程并输出正确选择器"""
    profile_dir = "data/browser_profiles/toutiao_account5"
    storage_file = os.path.join(profile_dir, "storage_state.json")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=storage_file) if os.path.exists(storage_file) else await browser.new_context()
        page = await context.new_page()

        results = {}  # 记录成功的选择器

        # 1. 打开发布页面
        print("\n[1] 打开发布页面...")
        await page.goto("https://mp.toutiao.com/profile_v4/graphic/publish")
        await asyncio.sleep(4)

        # 2. 填写标题
        print("[2] 填写标题...")
        try:
            await page.fill("textarea", TEST_TITLE)
            results["标题"] = "textarea"
            print("  ✓ 标题填写成功")
        except Exception as e:
            print(f"  ✗ 标题失败: {e}")
        await asyncio.sleep(2)

        # 3. 填写正文
        print("[3] 填写正文...")
        try:
            await page.fill(".ProseMirror", TEST_CONTENT)
            results["正文"] = ".ProseMirror"
            print("  ✓ 正文填写成功")
        except Exception as e:
            print(f"  ✗ 正文失败: {e}")
        await asyncio.sleep(3)

        # 4. 点击封面区域 - 使用用户提供的完整选择器
        print("[4] 查找并点击封面区域...")
        cover_selectors = [
            "#root > div > div.left-column > div > div.form-wrap > div.form-container > div:nth-child(1) > div > div.edit-input > div > div.article-cover-images-wrap > div.article-cover-images > div > div > div > div",
            ".article-cover-images-wrap .article-cover-images > div > div > div > div",
            ".article-cover-images-wrap",
        ]
        cover_clicked = False
        for sel in cover_selectors:
            try:
                cover_elem = await page.wait_for_selector(sel, timeout=3000)
                if cover_elem:
                    await cover_elem.click(force=True)
                    results["封面区域"] = sel
                    print(f"  ✓ 封面点击成功: {sel[:60]}...")
                    cover_clicked = True
                    break
            except:
                print(f"  ✗ 失败: {sel[:50]}...")
                continue
        if not cover_clicked:
            print("  所有封面选择器都失败")
        await asyncio.sleep(3)

        # 5. 点击"我的素材"
        print("[5] 点击'我的素材'标签...")
        try:
            await page.click("text=我的素材", timeout=5000)
            results["我的素材"] = "text=我的素材"
            print("  ✓ 已点击'我的素材'")
        except:
            print("  ✗ 'text=我的素材'失败，尝试其他方式...")
            try:
                await page.evaluate("""() => {
                    const tabs = document.querySelectorAll('.byte-tabs-tab');
                    for (let tab of tabs) {
                        if (tab.innerText.includes('我的素材')) {
                            tab.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                results["我的素材"] = "JS: .byte-tabs-tab contains 我的素材"
                print("  ✓ JS方式点击成功")
            except Exception as e:
                print(f"  ✗ 失败: {e}")
        await asyncio.sleep(2)

        # 6. 选择第一张图片
        print("[6] 选择图片...")
        img_sel = await page.evaluate("""() => {
            // 查找素材库中的图片
            const imgs = document.querySelectorAll('.byte-drawer img');
            if (imgs.length > 0) {
                imgs[0].click();
                return 'clicked: .byte-drawer img';
            }
            const spans = document.querySelectorAll('.byte-drawer .img-span');
            if (spans.length > 0) {
                spans[0].click();
                return 'clicked: .byte-drawer .img-span';
            }
            // 查找ReactVirtualized中的图片
            const vImg = document.querySelector('.ReactVirtualized__Grid img');
            if (vImg) {
                vImg.click();
                return 'clicked: .ReactVirtualized__Grid img';
            }
            return 'not found';
        }""")
        print(f"  图片选择: {img_sel}")
        if "clicked" in img_sel:
            results["素材图片"] = img_sel.replace("clicked: ", "")
        await asyncio.sleep(2)

        # 7. 点击确定按钮
        print("[7] 点击确定按钮...")
        confirm_sel = await page.evaluate("""() => {
            // 查找footer中的确定按钮
            const btns = document.querySelectorAll('.byte-drawer button');
            for (let btn of btns) {
                if (btn.innerText.includes('确定') || btn.innerText.includes('确 定')) {
                    btn.click();
                    return 'clicked: .byte-drawer button[确定]';
                }
            }
            // 查找primary按钮
            const primary = document.querySelector('.byte-drawer .byte-btn-primary');
            if (primary) {
                primary.click();
                return 'clicked: .byte-drawer .byte-btn-primary';
            }
            return 'not found';
        }""")
        print(f"  确定按钮: {confirm_sel}")
        if "clicked" in confirm_sel:
            results["确定按钮"] = confirm_sel.replace("clicked: ", "")
        await asyncio.sleep(3)

        # 8. 查找发布按钮（不点击）
        print("[8] 查找发布按钮...")
        try:
            pub = await page.wait_for_selector("button.publish-btn", timeout=3000)
            if pub:
                results["发布按钮"] = "button.publish-btn"
                print("  ✓ 找到发布按钮")
        except:
            print("  ✗ 未找到发布按钮")

        # 汇总结果
        print("\n" + "="*50)
        print("=== 检测结果汇总 ===")
        print("="*50)
        for k, v in results.items():
            print(f"{k}: {v}")
        print("="*50)

        input("\n按Enter关闭浏览器...")
        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_full_flow())

