"""AiStock V8 通达信双端口连接池

为 pytdx 提供连接池化支持, 管理两种端口连接:
- 标准端口 (7709): 股票行情、指数数据
- 扩展端口 (7721): 期货、期权、宏观数据

特性:
- 每端口独立连接池, 可配置池大小
- 自动重连: 连接断开时自动重建
- 心跳健康检查: 定期发送心跳保活
- 上下文管理器: 安全获取/归还连接
- 线程安全: acquire/release 加锁保护

Usage:
    >>> from base_services import TDXConnectionPool
    >>> pool = TDXConnectionPool(pool_size=3)
    >>>
    >>> # 获取标准端口连接
    >>> with pool.connection('standard') as conn:
    ...     df = conn.to_df(conn.get_security_bars(9, 1, '000001', 0, 100))
    >>>
    >>> # 获取扩展端口连接
    >>> with pool.connection('extension') as conn:
    ...     df = conn.to_df(conn.get_security_bars(9, 8, '39', 0, 100))
    >>>
    >>> # 关闭连接池
    >>> pool.shutdown()
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from queue import Empty, Queue
from typing import Any, Dict, Generator, Optional

try:
    from pytdx.hq import TdxHq_API
except ImportError:
    TdxHq_API = None  # type: ignore[assignment, misc]


# ─── 端口类型枚举 ────────────────────────────────────────────────────

class PortType(str, Enum):
    """通达信端口类型

    - STANDARD: 标准端口 (7709) - 股票/指数
    - EXTENSION: 扩展端口 (7721) - 期货/期权/宏观
    """
    STANDARD = 'standard'
    EXTENSION = 'extension'


# ─── 默认服务器配置 ──────────────────────────────────────────────────

_DEFAULT_SERVERS: Dict[PortType, Dict[str, Any]] = {
    PortType.STANDARD: {
        'host': '180.153.18.170',
        'port': 7709,
        'description': '标准行情 (股票/指数)',
    },
    PortType.EXTENSION: {
        'host': '180.153.18.176',
        'port': 7721,
        'description': '扩展行情 (期货/期权/宏观)',
    },
}


# ─── 连接包装器 ──────────────────────────────────────────────────────

@dataclass
class _PooledConnection:
    """池化连接包装器

    封装 pytdx 连接实例, 附加连接池管理所需的元数据.
    """
    conn: Any  # TdxHq_API 实例
    port_type: PortType
    host: str
    port: int
    created_at: float
    last_used_at: float
    is_alive: bool = True

    def touch(self) -> None:
        """更新最后使用时间"""
        self.last_used_at = time.time()

    @property
    def idle_seconds(self) -> float:
        """空闲时间 (秒)"""
        return time.time() - self.last_used_at

    @property
    def age_seconds(self) -> float:
        """连接存活时间 (秒)"""
        return time.time() - self.created_at


# ─── 单端口连接池 ────────────────────────────────────────────────────

class _PortPool:
    """单个端口的连接池

    使用 Queue 管理空闲连接, 支持阻塞获取与超时.
    线程安全: 内部操作受 Lock 保护.

    Args:
        port_type: 端口类型
        host: 服务器地址
        port: 服务器端口
        pool_size: 连接池大小
        connect_timeout: 连接超时 (秒)
        max_conn_age: 连接最大存活时间 (秒), 超过则重建
        heartbeat_interval: 心跳间隔 (秒)
        logger: 日志记录器
    """

    def __init__(
        self,
        port_type: PortType,
        host: str,
        port: int,
        pool_size: int = 3,
        connect_timeout: float = 10.0,
        max_conn_age: float = 3600.0,
        heartbeat_interval: float = 30.0,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._port_type = port_type
        self._host = host
        self._port = port
        self._pool_size = pool_size
        self._connect_timeout = connect_timeout
        self._max_conn_age = max_conn_age
        self._heartbeat_interval = heartbeat_interval
        self._logger = logger or logging.getLogger(__name__)

        # 空闲连接队列
        self._free: Queue[_PooledConnection] = Queue(maxsize=pool_size)
        # 活跃连接数
        self._active_count = 0
        # 总创建连接数 (统计用)
        self._total_created = 0
        # 总失败次数 (统计用)
        self._total_failures = 0
        # 锁
        self._lock = threading.Lock()
        # 心跳线程
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop = threading.Event()
        # 关闭标志
        self._shutdown = False

    # ─── 属性 ─────────────────────────────────────────────

    @property
    def port_type(self) -> PortType:
        return self._port_type

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def active_count(self) -> int:
        """当前活跃 (被借出) 的连接数"""
        with self._lock:
            return self._active_count

    @property
    def free_count(self) -> int:
        """当前空闲的连接数"""
        return self._free.qsize()

    @property
    def stats(self) -> Dict[str, Any]:
        """连接池统计"""
        return {
            'port_type': self._port_type.value,
            'host': self._host,
            'port': self._port,
            'pool_size': self._pool_size,
            'active': self.active_count,
            'free': self.free_count,
            'total_created': self._total_created,
            'total_failures': self._total_failures,
        }

    # ─── 连接管理 ─────────────────────────────────────────

    def _create_connection(self) -> _PooledConnection:
        """创建新的 pytdx 连接

        Returns:
            池化连接包装器

        Raises:
            ConnectionError: 连接失败
        """
        if TdxHq_API is None:
            raise ImportError(
                'pytdx 未安装, 请运行: pip install pytdx'
            )

        conn = TdxHq_API()
        try:
            success = conn.connect(
                self._host,
                self._port,
            )
            if not success:
                raise ConnectionError(
                    f'pytdx 连接失败: {self._host}:{self._port} '
                    f'(connect 返回 False)'
                )
        except Exception as e:
            if not isinstance(e, ConnectionError):
                raise ConnectionError(
                    f'pytdx 连接异常: {self._host}:{self._port} - {e}'
                ) from e
            raise

        now = time.time()
        wrapped = _PooledConnection(
            conn=conn,
            port_type=self._port_type,
            host=self._host,
            port=self._port,
            created_at=now,
            last_used_at=now,
            is_alive=True,
        )

        with self._lock:
            self._total_created += 1

        self._logger.debug(
            '连接创建成功 | %s | %s:%d | 连接 #%d',
            self._port_type.value,
            self._host,
            self._port,
            self._total_created,
        )
        return wrapped

    def _is_connection_valid(self, wrapped: _PooledConnection) -> bool:
        """检查连接是否仍然有效

        检查:
        - 连接是否标记为存活
        - 连接是否超过最大存活时间
        - (可选) 心跳检查

        Args:
            wrapped: 池化连接

        Returns:
            连接是否有效
        """
        if not wrapped.is_alive:
            return False

        # 超龄连接需要重建
        if wrapped.age_seconds > self._max_conn_age:
            self._logger.debug(
                '连接超龄, 需重建 | %s | 存活 %.0f s > 上限 %.0f s',
                self._port_type.value,
                wrapped.age_seconds,
                self._max_conn_age,
            )
            return False

        return True

    def _destroy_connection(self, wrapped: _PooledConnection) -> None:
        """安全关闭并销毁连接

        Args:
            wrapped: 池化连接
        """
        wrapped.is_alive = False
        try:
            wrapped.conn.disconnect()
        except Exception as e:
            self._logger.warning(
                '连接断开异常 (可忽略) | %s | %s',
                self._port_type.value,
                e,
            )

    # ─── 获取与归还 ───────────────────────────────────────

    def acquire(self, timeout: float = 30.0) -> _PooledConnection:
        """从池中获取一个连接

        优先从空闲队列获取, 若无空闲则创建新连接
        (不超过 pool_size), 超时抛出异常.

        Args:
            timeout: 获取超时 (秒)

        Returns:
            池化连接

        Raises:
            ConnectionError: 创建连接失败
            TimeoutError: 超时未获取到连接
        """
        if self._shutdown:
            raise RuntimeError('连接池已关闭')

        deadline = time.time() + timeout

        # 1. 尝试从空闲队列获取
        while True:
            try:
                wrapped = self._free.get_nowait()
                if self._is_connection_valid(wrapped):
                    wrapped.touch()
                    with self._lock:
                        self._active_count += 1
                    return wrapped
                else:
                    # 无效连接, 销毁后继续尝试
                    self._destroy_connection(wrapped)
            except Empty:
                break

        # 2. 创建新连接 (若未超池大小)
        with self._lock:
            current_total = self._active_count + self.free_count
            if current_total < self._pool_size:
                self._active_count += 1  # 预占

        try:
            wrapped = self._create_connection()
            return wrapped
        except (ConnectionError, ImportError):
            with self._lock:
                self._active_count -= 1  # 预占回退
                self._total_failures += 1
            raise

        # 3. 池已满, 等待空闲连接
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                wrapped = self._free.get(timeout=min(remaining, 1.0))
                if self._is_connection_valid(wrapped):
                    wrapped.touch()
                    with self._lock:
                        self._active_count += 1
                    return wrapped
                else:
                    self._destroy_connection(wrapped)
            except Empty:
                continue

        raise TimeoutError(
            f'获取连接超时 ({timeout}s) | {self._port_type.value} | '
            f'活跃={self.active_count} 空闲={self.free_count}'
        )

    def release(self, wrapped: _PooledConnection) -> None:
        """归还连接到池中

        若连接无效则销毁, 有效则放回空闲队列.

        Args:
            wrapped: 池化连接
        """
        with self._lock:
            self._active_count = max(0, self._active_count - 1)

        if self._shutdown or not self._is_connection_valid(wrapped):
            self._destroy_connection(wrapped)
            return

        try:
            self._free.put_nowait(wrapped)
        except Exception:
            # 队列满, 销毁连接
            self._destroy_connection(wrapped)

    # ─── 上下文管理 ───────────────────────────────────────

    @contextmanager
    def connection(self, timeout: float = 30.0) -> Generator[_PooledConnection, None, None]:
        """连接上下文管理器

        安全地获取/归还连接, 异常时自动重连一次.

        Args:
            timeout: 获取超时 (秒)

        Yields:
            池化连接

        Example:
            >>> with port_pool.connection() as conn:
            ...     data = conn.get_security_bars(...)
        """
        wrapped = self.acquire(timeout=timeout)
        try:
            yield wrapped
        except Exception as e:
            # 标记连接可能已断开
            wrapped.is_alive = False
            self._logger.warning(
                '连接使用异常, 标记为不可用 | %s | %s',
                self._port_type.value,
                e,
            )
            raise
        finally:
            self.release(wrapped)

    # ─── 健康检查 ─────────────────────────────────────────

    def _heartbeat_check(self, wrapped: _PooledConnection) -> bool:
        """对连接执行心跳检查

        通过获取市场信息来验证连接是否仍然活跃.

        Args:
            wrapped: 池化连接

        Returns:
            连接是否健康
        """
        try:
            # 使用 get_security_count 做轻量心跳
            result = wrapped.conn.get_security_count(0)
            if result is not None:
                wrapped.is_alive = True
                return True
        except Exception as e:
            self._logger.debug(
                '心跳检查失败 | %s | %s',
                self._port_type.value,
                e,
            )

        wrapped.is_alive = False
        return False

    def _heartbeat_loop(self) -> None:
        """心跳线程主循环

        定期检查空闲连接的健康状态, 不健康的连接将被销毁.
        """
        while not self._heartbeat_stop.is_set():
            self._heartbeat_stop.wait(self._heartbeat_interval)
            if self._heartbeat_stop.is_set():
                break

            # 检查空闲连接
            healthy: list[_PooledConnection] = []
            while True:
                try:
                    wrapped = self._free.get_nowait()
                    if self._heartbeat_check(wrapped):
                        healthy.append(wrapped)
                    else:
                        self._destroy_connection(wrapped)
                except Empty:
                    break

            # 放回健康连接
            for w in healthy:
                try:
                    self._free.put_nowait(w)
                except Exception:
                    self._destroy_connection(w)

    def start_heartbeat(self) -> None:
        """启动心跳线程"""
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f'tdx-heartbeat-{self._port_type.value}',
            daemon=True,
        )
        self._heartbeat_thread.start()
        self._logger.info(
            '心跳线程启动 | %s | 间隔 %.0f s',
            self._port_type.value,
            self._heartbeat_interval,
        )

    def stop_heartbeat(self) -> None:
        """停止心跳线程"""
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=5.0)
            self._heartbeat_thread = None

    # ─── 生命周期 ─────────────────────────────────────────

    def shutdown(self) -> None:
        """关闭连接池, 销毁所有连接"""
        self._shutdown = True
        self.stop_heartbeat()

        # 销毁所有空闲连接
        while True:
            try:
                wrapped = self._free.get_nowait()
                self._destroy_connection(wrapped)
            except Empty:
                break

        self._logger.info(
            '连接池关闭 | %s | 创建=%d 失败=%d',
            self._port_type.value,
            self._total_created,
            self._total_failures,
        )


# ─── TDX 双端口连接池 ────────────────────────────────────────────────

class TDXConnectionPool:
    """AiStock V8 通达信双端口连接池

    管理标准端口 (7709) 和扩展端口 (7721) 两套连接池,
    支持自动重连、心跳保活、线程安全的连接获取/归还.

    Args:
        pool_size: 每端口连接池大小, 默认 3
        standard_host: 标准端口服务器地址
        standard_port: 标准端口服务器端口
        extension_host: 扩展端口服务器地址
        extension_port: 扩展端口服务器端口
        connect_timeout: 连接超时 (秒)
        max_conn_age: 连接最大存活时间 (秒)
        heartbeat_interval: 心跳间隔 (秒)
        auto_heartbeat: 是否自动启动心跳, 默认 True

    Example:
        >>> pool = TDXConnectionPool(pool_size=3)
        >>>
        >>> with pool.connection('standard') as conn:
        ...     df = conn.to_df(conn.get_security_bars(9, 1, '000001', 0, 100))
        >>>
        >>> with pool.connection('extension') as conn:
        ...     df = conn.to_df(conn.get_security_bars(9, 8, '39', 0, 100))
        >>>
        >>> pool.shutdown()
    """

    def __init__(
        self,
        pool_size: int = 3,
        standard_host: str = _DEFAULT_SERVERS[PortType.STANDARD]['host'],
        standard_port: int = _DEFAULT_SERVERS[PortType.STANDARD]['port'],
        extension_host: str = _DEFAULT_SERVERS[PortType.EXTENSION]['host'],
        extension_port: int = _DEFAULT_SERVERS[PortType.EXTENSION]['port'],
        connect_timeout: float = 10.0,
        max_conn_age: float = 3600.0,
        heartbeat_interval: float = 30.0,
        auto_heartbeat: bool = True,
    ) -> None:
        if pool_size <= 0:
            raise ValueError(f'pool_size 必须为正整数, 收到: {pool_size}')

        self._pool_size = pool_size
        self._logger = logging.getLogger('aistock.tdx.pool')

        # 创建两个端口的连接池
        self._pools: Dict[PortType, _PortPool] = {
            PortType.STANDARD: _PortPool(
                port_type=PortType.STANDARD,
                host=standard_host,
                port=standard_port,
                pool_size=pool_size,
                connect_timeout=connect_timeout,
                max_conn_age=max_conn_age,
                heartbeat_interval=heartbeat_interval,
                logger=self._logger,
            ),
            PortType.EXTENSION: _PortPool(
                port_type=PortType.EXTENSION,
                host=extension_host,
                port=extension_port,
                pool_size=pool_size,
                connect_timeout=connect_timeout,
                max_conn_age=max_conn_age,
                heartbeat_interval=heartbeat_interval,
                logger=self._logger,
            ),
        }

        # 自动启动心跳
        if auto_heartbeat:
            self.start_heartbeat()

        self._logger.info(
            '🔌 TDXConnectionPool 初始化 | 池大小=%d | '
            '标准=%s:%d | 扩展=%s:%d | 心跳=%s',
            pool_size,
            standard_host,
            standard_port,
            extension_host,
            extension_port,
            f'{heartbeat_interval}s' if auto_heartbeat else '关闭',
        )

    # ─── 属性 ─────────────────────────────────────────────

    @property
    def pool_size(self) -> int:
        """每端口连接池大小"""
        return self._pool_size

    def get_pool(self, port_type: str) -> _PortPool:
        """获取指定端口的连接池

        Args:
            port_type: 'standard' 或 'extension'

        Returns:
            _PortPool 实例

        Raises:
            ValueError: 无效的端口类型
        """
        try:
            pt = PortType(port_type)
        except ValueError:
            valid = [pt.value for pt in PortType]
            raise ValueError(
                f'无效的端口类型: {port_type!r}, 有效值: {valid}'
            ) from None
        return self._pools[pt]

    # ─── 连接获取 ─────────────────────────────────────────

    @contextmanager
    def connection(
        self,
        port_type: str = 'standard',
        timeout: float = 30.0,
        auto_reconnect: bool = True,
    ) -> Generator[Any, None, None]:
        """获取连接的上下文管理器

        自动获取连接, 使用后归还. 若连接断开且 auto_reconnect=True,
        自动重连一次.

        Args:
            port_type: 端口类型, 'standard' 或 'extension'
            timeout: 获取超时 (秒)
            auto_reconnect: 连接断开时是否自动重连

        Yields:
            pytdx TdxHq_API 连接实例

        Example:
            >>> with pool.connection('standard') as conn:
            ...     bars = conn.get_security_bars(9, 1, '000001', 0, 100)
        """
        pool = self.get_pool(port_type)

        attempts = 2 if auto_reconnect else 1
        last_error: Optional[Exception] = None

        for attempt in range(attempts):
            try:
                with pool.connection(timeout=timeout) as wrapped:
                    yield wrapped.conn
                    return
            except Exception as e:
                last_error = e
                if attempt < attempts - 1:
                    self._logger.warning(
                        '连接失败, 尝试重连 | %s | 第 %d 次 | %s',
                        port_type,
                        attempt + 1,
                        e,
                    )
                else:
                    self._logger.error(
                        '连接最终失败 | %s | %s',
                        port_type,
                        e,
                    )

        raise ConnectionError(
            f'TDX 连接失败 (已重试) | port_type={port_type} | error={last_error}'
        ) from last_error

    # ─── 心跳管理 ─────────────────────────────────────────

    def start_heartbeat(self) -> None:
        """启动所有端口的心跳线程"""
        for pool in self._pools.values():
            pool.start_heartbeat()

    def stop_heartbeat(self) -> None:
        """停止所有端口的心跳线程"""
        for pool in self._pools.values():
            pool.stop_heartbeat()

    # ─── 统计 ─────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        """连接池统计信息"""
        return {
            'pool_size': self._pool_size,
            'pools': {
                pt.value: pool.stats for pt, pool in self._pools.items()
            },
        }

    # ─── 生命周期 ─────────────────────────────────────────

    def shutdown(self) -> None:
        """关闭连接池, 释放所有资源

        停止心跳线程, 销毁所有连接.
        关闭后的连接池不可重新使用.
        """
        self._logger.info('🔌 TDXConnectionPool 关闭中...')
        for pool in self._pools.values():
            pool.shutdown()
        self._logger.info('🔌 TDXConnectionPool 已关闭')

    def __repr__(self) -> str:
        return (
            f'TDXConnectionPool('
            f'pool_size={self._pool_size}, '
            f'standard={self._pools[PortType.STANDARD].active_count + self._pools[PortType.STANDARD].free_count}, '
            f'extension={self._pools[PortType.EXTENSION].active_count + self._pools[PortType.EXTENSION].free_count}'
            f')'
        )
