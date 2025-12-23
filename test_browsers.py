"""
测试脚本：打开两个独立浏览器窗口
- 今日头条账号6
- 搜狐-susu说流量
"""

import asyncio
from playwright.async_api import async_playwright
import os

# 浏览器配置目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BROWSER_PROFILES_DIR = os.path.join(BASE_DIR, "data", "browser_profiles")

async def open_browser(profile_dir: str, name: str, url: str):
    """打开一个浏览器窗口"""
    profile_path = os.path.join(BROWSER_PROFILES_DIR, profile_dir)
    storage_file = os.path.join(profile_path, "storage_state.json")
    
    print(f"正在打开浏览器: {name}")
    print(f"  配置目录: {profile_path}")
    print(f"  登录状态文件: {storage_file}")
    print(f"  登录状态文件存在: {os.path.exists(storage_file)}")
    
    playwright = await async_playwright().start()
    
    # 启动浏览器（有头模式）
    browser = await playwright.chromium.launch(
        headless=False,
        args=['--start-maximized']
    )
    
    # 创建上下文，如果有存储状态则加载
    context_options = {
        'viewport': None,  # 使用最大化窗口
    }
    
    if os.path.exists(storage_file):
        context_options['storage_state'] = storage_file
        print(f"  ✅ 已加载登录状态")
    else:
        print(f"  ⚠️ 无登录状态，需要手动登录")
    
    context = await browser.new_context(**context_options)
    page = await context.new_page()
    
    # 打开页面
    await page.goto(url)
    print(f"  已打开: {url}")
    
    return playwright, browser, context, page

async def main():
    print("=" * 60)
    print("测试两个账号的浏览器窗口")
    print("=" * 60)
    
    # 今日头条账号6
    toutiao_result = await open_browser(
        profile_dir="toutiao_account6",
        name="今日头条-账号6",
        url="https://mp.toutiao.com/profile_v4/index"
    )
    
    print()
    
    # 搜狐-susu说流量
    sohu_result = await open_browser(
        profile_dir="sohu_account2",
        name="搜狐-susu说流量",
        url="https://mp.sohu.com/mpfe/v4/main/index"
    )
    
    print()
    print("=" * 60)
    print("两个浏览器已打开，请检查登录状态")
    print("按 Ctrl+C 退出并关闭浏览器")
    print("=" * 60)
    
    # 保持运行，不要退出
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n正在关闭浏览器...")
        
        # 关闭浏览器
        await toutiao_result[2].close()  # context
        await toutiao_result[1].close()  # browser
        await toutiao_result[0].stop()   # playwright
        
        await sohu_result[2].close()
        await sohu_result[1].close()
        await sohu_result[0].stop()
        
        print("已关闭所有浏览器")

if __name__ == "__main__":
    asyncio.run(main())

