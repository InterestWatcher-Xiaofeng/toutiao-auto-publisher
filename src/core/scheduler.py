"""
任务调度器
管理发布任务的执行（支持并行发布）
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
    """任务调度器（支持并行发布）"""

    def __init__(self):
        self.excel_reader = ExcelReader()
        self.tasks: List[PublishTask] = []
        self.account_tasks: List[AccountTask] = []
        self._running = False
        self._cancelled = False
        self._adapters: Dict[str, BaseAdapter] = {}

        # 并行配置
        self.max_concurrent: int = 3  # 默认最大并发数

        # 回调函数
        self.on_task_start: Optional[Callable[[PublishTask], None]] = None
        self.on_task_complete: Optional[Callable[[PublishTask], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None
        self.on_progress: Optional[Callable[[int, int], None]] = None

        # 并行执行时的进度跟踪
        self._completed_count = 0
        self._total_count = 0
        self._progress_lock = asyncio.Lock() if asyncio.get_event_loop().is_running() else None
    
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

    def add_account(self, platform: str) -> AccountTask:
        """添加新账号

        Args:
            platform: 平台名称 ('toutiao' 或 'sohu')

        Returns:
            新创建的AccountTask对象
        """
        # 调用config添加账号
        new_acc = config.add_account(platform)

        # 创建AccountTask并添加到列表
        account_task = AccountTask(
            account_id=new_acc['id'],
            account_name=new_acc['name'],
            platform=new_acc['platform'],
            profile_dir=new_acc['profile_dir'],
            enabled=new_acc.get('enabled', True)
        )
        self.account_tasks.append(account_task)

        logger.info(f"已添加新账号: {account_task.account_name}")
        return account_task

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

    def set_max_concurrent(self, count: int):
        """设置最大并发数"""
        self.max_concurrent = max(1, min(count, 10))  # 限制1-10
        self._log(f"设置并发数: {self.max_concurrent}")

    async def run(self):
        """运行所有任务（并行模式）"""
        if self._running:
            logger.warning("调度器已在运行中")
            return

        self._running = True
        self._cancelled = False
        self._completed_count = 0
        self._total_count = len(self.tasks)

        self._log(f"开始执行 {self._total_count} 个发布任务（并发数: {self.max_concurrent}）...")

        # 按账号分组任务
        account_task_groups: Dict[str, List[PublishTask]] = {}
        for task in self.tasks:
            if task.account_id not in account_task_groups:
                account_task_groups[task.account_id] = []
            account_task_groups[task.account_id].append(task)

        self._log(f"共 {len(account_task_groups)} 个账号参与发布")

        # 创建信号量控制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent)

        # 为每个账号创建并行任务
        account_coroutines = []
        for account_id, tasks in account_task_groups.items():
            coro = self._run_account_tasks(account_id, tasks, semaphore)
            account_coroutines.append(coro)

        # 并行执行所有账号的任务
        await asyncio.gather(*account_coroutines, return_exceptions=True)

        self._running = False

        # 统计结果
        success_count = sum(1 for t in self.tasks if t.status == TaskStatus.SUCCESS)
        failed_count = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        self._log(f"🎉 发布完成! 成功: {success_count}, 失败: {failed_count}")
        self._log("所有任务已完成!")
        self._adapters.clear()

    async def _run_account_tasks(self, account_id: str, tasks: List[PublishTask], semaphore: asyncio.Semaphore):
        """运行单个账号的所有任务"""
        async with semaphore:
            if self._cancelled:
                return

            account_name = tasks[0].account_name if tasks else account_id
            self._log(f"🚀 [{account_name}] 开始发布 {len(tasks)} 篇文章...")

            try:
                # 获取适配器
                adapter = self._get_adapter(tasks[0])

                # 检查登录状态
                if self._cancelled:
                    return

                is_logged_in = await adapter.check_login_status()

                if not is_logged_in:
                    self._log(f"[{account_name}] 需要登录，请在浏览器中手动登录...")
                    login_success = await adapter.wait_for_login()
                    if self._cancelled:
                        return
                    if not login_success:
                        for task in tasks:
                            task.status = TaskStatus.FAILED
                            task.result = {'success': False, 'message': '登录超时'}
                            await self._update_progress(task)
                        self._log(f"❌ [{account_name}] 登录失败，跳过该账号所有任务")
                        return

                # 依次发布该账号的文章
                for task in tasks:
                    if self._cancelled:
                        break

                    await self._execute_single_task(task, adapter)

            except Exception as e:
                self._log(f"❌ [{account_name}] 账号执行异常: {e}")
                for task in tasks:
                    if task.status == TaskStatus.PENDING:
                        task.status = TaskStatus.FAILED
                        task.result = {'success': False, 'message': str(e)}
                        await self._update_progress(task)

            self._log(f"✅ [{account_name}] 该账号任务完成")

    async def _execute_single_task(self, task: PublishTask, adapter: BaseAdapter):
        """执行单个发布任务"""
        import random

        task.status = TaskStatus.RUNNING
        if self.on_task_start:
            self.on_task_start(task)

        self._log(f"📝 [{task.account_name}] 正在发布: {task.article.title[:30]}...")

        try:
            if self._cancelled:
                return

            # 发布文章
            result = await adapter.publish_article(task.article)
            task.result = result

            if result['success']:
                task.status = TaskStatus.SUCCESS
                self.excel_reader.mark_as_published(task.article, "success")
                self._log(f"✅ [{task.account_name}] 发布成功: {task.article.title[:30]}...")
            else:
                task.status = TaskStatus.FAILED
                self._log(f"❌ [{task.account_name}] 发布失败: {result['message']}")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.result = {'success': False, 'message': str(e)}
            self._log(f"❌ [{task.account_name}] 发布异常: {e}")

        await self._update_progress(task)

        # 任务间随机延迟
        if not self._cancelled:
            delay = random.uniform(2, 5)
            await asyncio.sleep(delay)

    async def _update_progress(self, task: PublishTask):
        """更新进度（线程安全）"""
        self._completed_count += 1

        if self.on_progress:
            self.on_progress(self._completed_count, self._total_count)

        if self.on_task_complete:
            self.on_task_complete(task)

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

