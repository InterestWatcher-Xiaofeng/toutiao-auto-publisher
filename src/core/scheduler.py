"""
任务调度器
管理发布任务的执行
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum

from src.core.logger import get_logger
from src.adapters.base_adapter import BaseAdapter
from src.adapters.toutiao_adapter import ToutiaoAdapter
from src.adapters.sohu_adapter import SohuAdapter
from src.utils.excel_reader import Article, ExcelReader
from src.utils.config import config

logger = get_logger()


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PublishTask:
    """发布任务"""
    account_id: str
    account_name: str
    platform: str
    article: Article
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None


@dataclass
class AccountTask:
    """账号任务配置"""
    account_id: str
    account_name: str
    platform: str
    profile_dir: str
    publish_count: int = 0
    enabled: bool = True


class Scheduler:
    """任务调度器"""
    
    def __init__(self):
        self.excel_reader = ExcelReader()
        self.tasks: List[PublishTask] = []
        self.account_tasks: List[AccountTask] = []
        self._running = False
        self._cancelled = False
        self._adapters: Dict[str, BaseAdapter] = {}
        
        # 回调函数
        self.on_task_start: Optional[Callable[[PublishTask], None]] = None
        self.on_task_complete: Optional[Callable[[PublishTask], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None
        self.on_progress: Optional[Callable[[int, int], None]] = None
    
    def load_accounts(self) -> List[AccountTask]:
        """加载所有账号"""
        accounts = config.get_accounts()
        self.account_tasks = []
        
        for acc in accounts:
            account_task = AccountTask(
                account_id=acc['id'],
                account_name=acc['name'],
                platform=acc['platform'],
                profile_dir=acc['profile_dir'],
                enabled=acc.get('enabled', True)
            )
            self.account_tasks.append(account_task)
        
        return self.account_tasks
    
    def load_articles(self, file_path: str) -> bool:
        """加载文章"""
        return self.excel_reader.load(file_path)
    
    def get_articles(self) -> List[Article]:
        """获取所有文章"""
        return self.excel_reader.get_articles()
    
    def set_account_publish_count(self, account_id: str, count: int):
        """设置账号发布数量"""
        for task in self.account_tasks:
            if task.account_id == account_id:
                task.publish_count = count
                logger.info(f"设置 {task.account_name} 发布数量: {count}")
                break
    
    def generate_tasks(self) -> List[PublishTask]:
        """生成发布任务队列"""
        self.tasks = []
        article_index = 0
        articles = self.excel_reader.get_articles()
        
        # 按账号生成任务
        for account_task in self.account_tasks:
            if not account_task.enabled or account_task.publish_count <= 0:
                continue
            
            for i in range(account_task.publish_count):
                if article_index >= len(articles):
                    logger.warning("文章数量不足，停止生成任务")
                    break
                
                article = articles[article_index]
                task = PublishTask(
                    account_id=account_task.account_id,
                    account_name=account_task.account_name,
                    platform=account_task.platform,
                    article=article
                )
                self.tasks.append(task)
                article_index += 1
        
        logger.info(f"共生成 {len(self.tasks)} 个发布任务")
        return self.tasks
    
    def _get_adapter(self, task: PublishTask) -> BaseAdapter:
        """获取或创建适配器"""
        if task.account_id in self._adapters:
            return self._adapters[task.account_id]
        
        account = config.get_account_by_id(task.account_id)
        profile_dir = account['profile_dir'] if account else task.account_id
        
        if task.platform == 'toutiao':
            adapter = ToutiaoAdapter(task.account_id, profile_dir, task.account_name)
        elif task.platform == 'sohu':
            adapter = SohuAdapter(task.account_id, profile_dir, task.account_name)
        else:
            raise ValueError(f"不支持的平台: {task.platform}")
        
        self._adapters[task.account_id] = adapter
        return adapter
    
    def _log(self, message: str):
        """记录日志"""
        logger.info(message)
        if self.on_log:
            self.on_log(message)

    async def run(self):
        """运行所有任务"""
        if self._running:
            logger.warning("调度器已在运行中")
            return

        self._running = True
        self._cancelled = False
        total = len(self.tasks)
        completed = 0

        self._log(f"开始执行 {total} 个发布任务...")

        for task in self.tasks:
            if self._cancelled:
                self._log("任务已取消")
                break

            task.status = TaskStatus.RUNNING
            if self.on_task_start:
                self.on_task_start(task)

            self._log(f"正在发布: [{task.account_name}] {task.article.title[:30]}...")

            try:
                # 再次检查取消状态
                if self._cancelled:
                    self._log("任务已取消")
                    break

                adapter = self._get_adapter(task)

                # 检查登录状态
                if self._cancelled:
                    break
                is_logged_in = await adapter.check_login_status()

                if self._cancelled:
                    break

                if not is_logged_in:
                    self._log(f"[{task.account_name}] 需要登录，请在浏览器中手动登录...")
                    login_success = await adapter.wait_for_login()
                    if self._cancelled:
                        break
                    if not login_success:
                        task.status = TaskStatus.FAILED
                        task.result = {'success': False, 'message': '登录超时'}
                        self._log(f"[{task.account_name}] 登录失败，跳过此任务")
                        continue

                # 再次检查取消状态
                if self._cancelled:
                    break

                # 发布文章
                result = await adapter.publish_article(task.article)
                task.result = result

                if result['success']:
                    task.status = TaskStatus.SUCCESS
                    self.excel_reader.mark_as_published(task.article, "success")
                    self._log(f"✅ 发布成功: {task.article.title[:30]}...")
                else:
                    task.status = TaskStatus.FAILED
                    self._log(f"❌ 发布失败: {result['message']}")

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.result = {'success': False, 'message': str(e)}
                self._log(f"❌ 发布异常: {e}")

            completed += 1
            if self.on_progress:
                self.on_progress(completed, total)

            if self.on_task_complete:
                self.on_task_complete(task)

            # 任务间随机延迟
            if completed < total and not self._cancelled:
                import random
                delay = random.uniform(3, 8)
                self._log(f"等待 {delay:.1f} 秒后继续...")
                await asyncio.sleep(delay)

        self._running = False

        # 统计结果
        success_count = sum(1 for t in self.tasks if t.status == TaskStatus.SUCCESS)
        failed_count = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        self._log(f"发布完成! 成功: {success_count}, 失败: {failed_count}")

        # 注意：不在这里关闭浏览器，让用户可以查看结果
        # 浏览器将在程序退出时自动关闭
        self._log("所有任务已完成!")
        self._adapters.clear()

    def cancel(self):
        """取消任务"""
        self._cancelled = True
        self._running = False
        self._log("正在取消任务...")

        # 通知所有适配器取消
        for adapter in self._adapters.values():
            try:
                if hasattr(adapter, 'cancel'):
                    adapter.cancel()
            except Exception:
                pass

    def reset(self):
        """重置调度器状态（在新任务开始前调用）"""
        self._running = False
        self._cancelled = False
        self._adapters.clear()
        # 重置所有任务状态
        for task in self.tasks:
            task.status = TaskStatus.PENDING
            task.result = None

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running


# 全局调度器实例
scheduler = Scheduler()

