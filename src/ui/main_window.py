"""
主窗口
"""

import asyncio
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QSpinBox, QTextEdit, QFileDialog, QMessageBox,
    QProgressBar, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor

from src.core.scheduler import scheduler, PublishTask, TaskStatus
from src.core.logger import get_logger

logger = get_logger()


class AsyncWorker(QThread):
    """异步任务工作线程"""
    finished = Signal()
    error = Signal(str)
    log_message = Signal(str)
    progress = Signal(int, int)
    task_updated = Signal(object)

    def __init__(self, task_type: str = "publish", **kwargs):
        super().__init__()
        self._loop = None
        self._task_type = task_type  # "publish" 或 "login"
        self._kwargs = kwargs

    def run(self):
        """运行异步任务"""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            if self._task_type == "publish":
                self._run_publish_task()
            elif self._task_type == "login":
                self._run_login_task()

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            # 不关闭loop，因为浏览器可能还在使用
            pass

    def _run_publish_task(self):
        """运行发布任务"""
        from src.browser.browser_manager import browser_manager

        # 设置回调
        scheduler.on_log = lambda msg: self.log_message.emit(msg)
        scheduler.on_progress = lambda c, t: self.progress.emit(c, t)
        scheduler.on_task_complete = lambda t: self.task_updated.emit(t)

        # 在新的 event loop 中，强制重新初始化浏览器
        # 这是因为 Playwright 资源绑定到创建它们的 event loop
        self._loop.run_until_complete(browser_manager.reinitialize_for_new_loop())

        self._loop.run_until_complete(scheduler.run())

    def _run_login_task(self):
        """运行登录任务"""
        from src.adapters.toutiao_adapter import ToutiaoAdapter
        from src.adapters.sohu_adapter import SohuAdapter
        from src.browser.browser_manager import browser_manager

        account_id = self._kwargs.get('account_id')
        account_name = self._kwargs.get('account_name')
        platform = self._kwargs.get('platform')
        profile_dir = self._kwargs.get('profile_dir')

        if platform == 'toutiao':
            adapter = ToutiaoAdapter(account_id, profile_dir, account_name)
        else:
            adapter = SohuAdapter(account_id, profile_dir, account_name)

        result = self._loop.run_until_complete(adapter.wait_for_login())

        # wait_for_login 现在返回 (success, nickname) 元组
        if isinstance(result, tuple):
            success, nickname = result
        else:
            # 兼容旧版本返回bool的情况
            success = result
            nickname = ""

        # 登录成功后，关闭浏览器以释放资源
        # 登录状态已保存到 storage_state.json，发布时会重新加载
        self._loop.run_until_complete(browser_manager.cleanup())

        self._kwargs['success'] = success
        self._kwargs['nickname'] = nickname


class MainWindow(QMainWindow):
    """主窗口"""

    # 自定义信号
    _login_finished_signal = Signal(bool, str)  # success, nickname

    def __init__(self):
        super().__init__()
        self.worker = None
        self._current_login_btn = None

        # 连接信号
        self._login_finished_signal.connect(self._on_login_finished)

        self.init_ui()
        self.load_accounts()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("内容自动发布系统 v1.0")
        self.setMinimumSize(1200, 800)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 顶部工具栏
        toolbar = self._create_toolbar()
        main_layout.addLayout(toolbar)
        
        # 内容区域 - 使用分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：账号列表
        left_panel = self._create_account_panel()
        splitter.addWidget(left_panel)
        
        # 中间：任务配置
        center_panel = self._create_task_panel()
        splitter.addWidget(center_panel)
        
        # 右侧：内容预览
        right_panel = self._create_content_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([300, 400, 400])
        main_layout.addWidget(splitter, 1)
        
        # 底部：日志区域
        log_panel = self._create_log_panel()
        main_layout.addWidget(log_panel)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
    
    def _create_toolbar(self) -> QHBoxLayout:
        """创建工具栏"""
        layout = QHBoxLayout()
        
        # 导入表格按钮
        self.import_btn = QPushButton("📂 导入Excel表格")
        self.import_btn.setMinimumHeight(40)
        self.import_btn.clicked.connect(self.import_excel)
        layout.addWidget(self.import_btn)
        
        # 文件路径显示
        self.file_label = QLabel("未选择文件")
        layout.addWidget(self.file_label, 1)
        
        # 开始按钮
        self.start_btn = QPushButton("▶️ 开始发布")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_btn.clicked.connect(self.start_publish)
        layout.addWidget(self.start_btn)
        
        # 停止按钮
        self.stop_btn = QPushButton("⏹️ 停止")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.stop_btn.clicked.connect(self.stop_publish)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        return layout
    
    def _create_account_panel(self) -> QGroupBox:
        """创建账号面板"""
        group = QGroupBox("账号列表 (点击登录按钮进行登录)")
        layout = QVBoxLayout(group)

        # 账号表格（带登录按钮）
        self.account_table = QTableWidget()
        self.account_table.setColumnCount(3)
        self.account_table.setHorizontalHeaderLabels(["选择", "账号名称", "操作"])
        self.account_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.account_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.account_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.account_table.setColumnWidth(0, 50)
        self.account_table.setColumnWidth(2, 80)
        layout.addWidget(self.account_table)

        # 保留旧的list用于兼容
        self.account_list = QListWidget()
        self.account_list.setVisible(False)

        return group
    
    def _create_task_panel(self) -> QGroupBox:
        """创建任务配置面板"""
        group = QGroupBox("发布配置")
        layout = QVBoxLayout(group)

        # 任务配置表格
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(3)
        self.task_table.setHorizontalHeaderLabels(["账号", "发布数量", "状态"])
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.task_table)

        return group

    def _create_content_panel(self) -> QGroupBox:
        """创建内容预览面板"""
        group = QGroupBox("文章列表")
        layout = QVBoxLayout(group)

        # 文章数量
        self.article_count_label = QLabel("已导入: 0 篇文章")
        layout.addWidget(self.article_count_label)

        # 文章列表
        self.article_list = QListWidget()
        layout.addWidget(self.article_list)

        return group

    def _create_log_panel(self) -> QGroupBox:
        """创建日志面板"""
        group = QGroupBox("运行日志")
        group.setMaximumHeight(200)
        layout = QVBoxLayout(group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)

        return group

    def load_accounts(self):
        """加载账号列表"""
        accounts = scheduler.load_accounts()
        self.account_table.setRowCount(len(accounts))
        self.task_table.setRowCount(len(accounts))

        for i, acc in enumerate(accounts):
            # 添加到账号表格
            # 选择框
            checkbox = QCheckBox()
            checkbox.setChecked(acc.enabled)
            checkbox.setProperty("account_id", acc.account_id)
            checkbox.stateChanged.connect(self.on_account_checkbox_changed)
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.account_table.setCellWidget(i, 0, checkbox_widget)

            # 账号名称
            name_item = QTableWidgetItem(acc.account_name)
            name_item.setData(Qt.UserRole, acc.account_id)
            self.account_table.setItem(i, 1, name_item)

            # 登录按钮
            login_btn = QPushButton("登录")
            login_btn.setProperty("account_id", acc.account_id)
            login_btn.setProperty("account_name", acc.account_name)
            login_btn.setProperty("platform", acc.platform)
            login_btn.setProperty("profile_dir", acc.profile_dir)
            login_btn.clicked.connect(self.on_login_btn_clicked)
            self.account_table.setCellWidget(i, 2, login_btn)

            # 添加到任务配置表
            task_name_item = QTableWidgetItem(acc.account_name)
            task_name_item.setData(Qt.UserRole, acc.account_id)  # 保存account_id以便后续更新
            self.task_table.setItem(i, 0, task_name_item)

            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(0)
            spin.setProperty("account_id", acc.account_id)
            spin.valueChanged.connect(self.on_count_changed)
            self.task_table.setCellWidget(i, 1, spin)

            self.task_table.setItem(i, 2, QTableWidgetItem("待配置"))

        self.log("已加载 {} 个账号".format(len(accounts)))

    def on_account_checkbox_changed(self, state):
        """账号复选框状态变化"""
        checkbox = self.sender()
        account_id = checkbox.property("account_id")
        enabled = state == Qt.Checked.value

        for acc in scheduler.account_tasks:
            if acc.account_id == account_id:
                acc.enabled = enabled
                break

    def on_login_btn_clicked(self):
        """点击登录按钮"""
        btn = self.sender()
        account_id = btn.property("account_id")
        account_name = btn.property("account_name")
        platform = btn.property("platform")
        profile_dir = btn.property("profile_dir")

        self.log(f"正在打开登录页面: {account_name}")
        btn.setText("登录中...")
        btn.setEnabled(False)

        # 保存按钮引用用于后续更新
        self._current_login_btn = btn

        # 使用工作线程进行登录
        self._login_worker = AsyncWorker(
            task_type="login",
            account_id=account_id,
            account_name=account_name,
            platform=platform,
            profile_dir=profile_dir
        )
        self._login_worker.finished.connect(self._on_login_worker_finished)
        self._login_worker.error.connect(lambda e: self._login_finished_signal.emit(False, ""))
        self._login_worker.start()

    def _on_login_worker_finished(self):
        """登录工作线程完成"""
        success = getattr(self._login_worker, '_kwargs', {}).get('success', False)
        nickname = getattr(self._login_worker, '_kwargs', {}).get('nickname', "")
        self._login_finished_signal.emit(success, nickname)

    def _on_login_finished(self, success: bool, nickname: str):
        """登录完成回调（在主线程中执行）"""
        btn = getattr(self, '_current_login_btn', None)
        if btn:
            account_id = btn.property("account_id")

            if success:
                btn.setText("已登录 ✓")
                btn.setStyleSheet("background-color: #4CAF50; color: white;")

                # 如果获取到昵称，更新显示
                if nickname:
                    self._update_account_nickname(account_id, nickname)
                    self.log(f"登录成功！账号昵称: {nickname}")
                else:
                    self.log("登录成功！")
            else:
                btn.setText("登录")
                btn.setStyleSheet("")
                self.log("登录失败或超时")
            btn.setEnabled(True)

    def _update_account_nickname(self, account_id: str, nickname: str):
        """更新账号昵称显示和配置"""
        from src.utils.config import config

        # 更新账号表格中的显示
        for row in range(self.account_table.rowCount()):
            name_item = self.account_table.item(row, 1)
            if name_item and name_item.data(Qt.UserRole) == account_id:
                # 获取平台前缀
                platform = ""
                for acc in scheduler.account_tasks:
                    if acc.account_id == account_id:
                        platform = acc.platform
                        break

                # 组合新名称：平台-昵称
                platform_prefix = "今日头条" if platform == "toutiao" else "搜狐"
                new_name = f"{platform_prefix}-{nickname}"
                name_item.setText(new_name)
                break

        # 更新任务配置表格中的显示
        for row in range(self.task_table.rowCount()):
            task_item = self.task_table.item(row, 0)
            if task_item and task_item.data(Qt.UserRole) == account_id:
                platform = ""
                for acc in scheduler.account_tasks:
                    if acc.account_id == account_id:
                        platform = acc.platform
                        break
                platform_prefix = "今日头条" if platform == "toutiao" else "搜狐"
                new_name = f"{platform_prefix}-{nickname}"
                task_item.setText(new_name)
                break

        # 更新scheduler中的账号名称
        for acc in scheduler.account_tasks:
            if acc.account_id == account_id:
                platform_prefix = "今日头条" if acc.platform == "toutiao" else "搜狐"
                acc.account_name = f"{platform_prefix}-{nickname}"
                break

        # 保存到配置文件
        config.update_account_nickname(account_id, nickname)

    def import_excel(self):
        """导入Excel或CSV文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", "表格文件 (*.xlsx *.xls *.csv);;Excel文件 (*.xlsx *.xls);;CSV文件 (*.csv)"
        )

        if file_path:
            if scheduler.load_articles(file_path):
                self.file_label.setText(file_path)
                articles = scheduler.get_articles()
                self.article_count_label.setText(f"已导入: {len(articles)} 篇文章")

                # 显示文章列表
                self.article_list.clear()
                for article in articles:
                    self.article_list.addItem(f"{article.index}. {article.title}")

                self.log(f"成功导入 {len(articles)} 篇文章")
            else:
                QMessageBox.warning(self, "导入失败", "无法读取Excel文件")

    def on_count_changed(self, value: int):
        """发布数量变化"""
        spin = self.sender()
        account_id = spin.property("account_id")
        scheduler.set_account_publish_count(account_id, value)

    def start_publish(self):
        """开始发布"""
        # 检查是否已导入文章
        if not scheduler.get_articles():
            QMessageBox.warning(self, "提示", "请先导入Excel文件")
            return

        # 生成任务
        tasks = scheduler.generate_tasks()
        if not tasks:
            QMessageBox.warning(self, "提示", "请设置账号的发布数量")
            return

        # 重置scheduler状态（清除之前的取消标志和适配器）
        scheduler.reset()

        # 更新UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(tasks))
        self.progress_bar.setValue(0)

        self.log(f"开始执行 {len(tasks)} 个发布任务...")

        # 启动工作线程
        self.worker = AsyncWorker()
        self.worker.log_message.connect(self.log)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def stop_publish(self):
        """停止发布：尽量做到快速且优雅地终止当前任务"""
        self.log("正在停止...")
        # 通知调度器和各适配器设置取消标志
        scheduler.cancel()

        # 优先尝试在工作线程自己的事件循环中关闭浏览器，避免跨事件循环错误
        if hasattr(self, 'worker') and self.worker is not None:
            from src.browser.browser_manager import browser_manager
            try:
                import asyncio
                worker_loop = getattr(self.worker, "_loop", None)
                if worker_loop is not None and not worker_loop.is_closed():
                    # 在工作线程的事件循环中调度 close_all
                    future = asyncio.run_coroutine_threadsafe(
                        browser_manager.close_all(), worker_loop
                    )
                    try:
                        # 最多等待 5 秒关闭浏览器
                        future.result(timeout=5)
                    except Exception as e:  # pragma: no cover - 防御性日志
                        self.log(f"等待浏览器关闭时出错: {e}")
                else:
                    # 退化方案：当前拿不到有效事件循环时，使用临时事件循环关闭
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(browser_manager.close_all())
                    finally:
                        loop.close()
            except Exception as e:  # pragma: no cover - 防御性日志
                self.log(f"关闭浏览器时出错: {e}")

            # 等待工作线程优雅退出，如果 2 秒内仍未退出再强制终止
            if self.worker.isRunning():
                if not self.worker.wait(2000):
                    self.worker.terminate()
                    self.worker.wait(2000)

        # 更新UI状态
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log("已停止")

    def on_progress(self, current: int, total: int):
        """进度更新"""
        self.progress_bar.setValue(current)

    def on_finished(self):
        """任务完成"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log("所有任务已完成!")
        QMessageBox.information(self, "完成", "发布任务已完成!")

    def on_error(self, error: str):
        """任务出错"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log(f"错误: {error}")
        QMessageBox.critical(self, "错误", error)

    def log(self, message: str):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # 滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
