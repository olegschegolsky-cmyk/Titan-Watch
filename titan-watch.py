import asyncio
import functools
import os
import signal
import sys
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Type
from abc import ABC, ABCMeta, abstractmethod

import psutil

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    CLEAR_SCREEN = "\033[2J"
    CURSOR_HOME = "\033[H"
    HIDE_CURSOR = "\033[?25l"
    SHOW_CURSOR = "\033[?25h"

def profile_time(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        wrapper.last_execution_time = end_time - start_time
        return result
    return wrapper

class RingBuffer:
    __slots__ = ('capacity', 'data', 'index', 'is_full', '_running_sum')

    def __init__(self, capacity: int = 60):
        self.capacity = capacity
        self.data: List[float] = [0.0] * capacity
        self.index: int = 0
        self.is_full: bool = False
        self._running_sum: float = 0.0

    @profile_time
    def append(self, value: float) -> None:
        old_value = self.data[self.index]
        self.data[self.index] = value
        
        if self.is_full:
            self._running_sum += (value - old_value)
        else:
            self._running_sum += value

        self.index += 1
        if self.index >= self.capacity:
            self.is_full = True
            self.index = 0

    @property
    def moving_average(self) -> float:
        count = self.capacity if self.is_full else self.index
        return self._running_sum / count if count > 0 else 0.0

    def get_ordered_data(self) -> List[float]:
        if not self.is_full:
            return self.data[:self.index]
        return self.data[self.index:] + self.data[:self.index]

class MetricValue:
    __slots__ = ('name', 'value', 'unit', 'buffer')

    def __init__(self, name: str, unit: str, buffer_size: int = 60):
        self.name = name
        self.value: float = 0.0
        self.unit = unit
        self.buffer = RingBuffer(buffer_size)

    def update(self, val: float) -> None:
        self.value = val
        self.buffer.append(val)

class CollectorRegistry(ABCMeta):
    registry: List[Type['BaseCollector']] = []

    def __new__(mcs, name: str, bases: tuple, attrs: dict) -> type:
        new_class = super().__new__(mcs, name, bases, attrs)
        if name != "BaseCollector":
            mcs.registry.append(new_class)
        return new_class

class ResourceContext:
    def __init__(self, name: str):
        self.name = name

    def __enter__(self) -> 'ResourceContext':
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type:
            pass

class BaseCollector(ABC, metaclass=CollectorRegistry):
    def __init__(self) -> None:
        self.metrics: Dict[str, MetricValue] = self.setup_metrics()

    @abstractmethod
    def setup_metrics(self) -> Dict[str, MetricValue]:
        pass

    @abstractmethod
    def collect(self) -> None:
        pass

class CPUCollector(BaseCollector):
    def setup_metrics(self) -> Dict[str, MetricValue]:
        return {"usage": MetricValue("CPU Usage", "%")}

    def collect(self) -> None:
        with ResourceContext("CPU"):
            usage = psutil.cpu_percent(interval=None)
            self.metrics["usage"].update(usage)

class MemCollector(BaseCollector):
    def setup_metrics(self) -> Dict[str, MetricValue]:
        return {"usage": MetricValue("RAM Usage", "%")}

    def collect(self) -> None:
        with ResourceContext("Memory"):
            mem = psutil.virtual_memory()
            self.metrics["usage"].update(mem.percent)

class NetCollector(BaseCollector):
    __slots__ = ('last_sent', 'last_recv', 'last_time', 'metrics')

    def __init__(self) -> None:
        self.last_sent: int = 0
        self.last_recv: int = 0
        self.last_time: float = time.time()
        super().__init__()

    def setup_metrics(self) -> Dict[str, MetricValue]:
        return {
            "tx": MetricValue("Net TX", "MB/s"),
            "rx": MetricValue("Net RX", "MB/s")
        }

    def collect(self) -> None:
        with ResourceContext("Network"):
            net = psutil.net_io_counters()
            current_time = time.time()
            
            if self.last_time > 0:
                dt = current_time - self.last_time
                if dt > 0:
                    tx_speed = (net.bytes_sent - self.last_sent) / dt / (1024 * 1024)
                    rx_speed = (net.bytes_recv - self.last_recv) / dt / (1024 * 1024)
                    
                    self.metrics["tx"].update(tx_speed)
                    self.metrics["rx"].update(rx_speed)
            
            self.last_sent = net.bytes_sent
            self.last_recv = net.bytes_recv
            self.last_time = current_time

class DiskCollector(BaseCollector):
    def setup_metrics(self) -> Dict[str, MetricValue]:
        return {"usage": MetricValue("Disk Usage", "%")}

    def collect(self) -> None:
        with ResourceContext("Disk"):
            usage = psutil.disk_usage('/').percent
            self.metrics["usage"].update(usage)

class TerminalRenderer:
    BRAILLE_CHARS = [' ', '⡀', '⡄', '⡆', '⡇', '⣇', '⣧', '⣷', '⣿']

    def __init__(self) -> None:
        self._setup_terminal()

    def _setup_terminal(self) -> None:
        sys.stdout.write(Colors.HIDE_CURSOR + Colors.CLEAR_SCREEN)
        sys.stdout.flush()

    def cleanup(self) -> None:
        sys.stdout.write(Colors.SHOW_CURSOR + Colors.RESET + "\n")
        sys.stdout.flush()

    def _generate_sparkline(self, buffer: RingBuffer, width: int = 20) -> str:
        data = buffer.get_ordered_data()
        if not data:
            return " " * width
        
        data = data[-width:]
        if len(data) < width:
            data = [0.0] * (width - len(data)) + data
            
        min_val, max_val = min(data), max(data)
        diff = max_val - min_val if max_val != min_val else 1.0
        
        line = []
        for val in data:
            normalized = int(((val - min_val) / diff) * 8)
            normalized = max(0, min(8, normalized))
            line.append(self.BRAILLE_CHARS[normalized])
            
        return "".join(line)

    def render(self, collectors: List[BaseCollector]) -> None:
        frame_buffer: List[str] = []
        frame_buffer.append(Colors.CURSOR_HOME)
        
        frame_buffer.append(f"{Colors.BOLD}{Colors.CYAN}=== TITAN-WATCH: Distributed Resource Monitor ==={Colors.RESET}\n\n")
        
        for collector in collectors:
            class_name = collector.__class__.__name__.replace('Collector', '')
            frame_buffer.append(f"{Colors.BOLD}{Colors.YELLOW}[ {class_name} ]{Colors.RESET}\n")
            
            for key, metric in collector.metrics.items():
                sparkline = self._generate_sparkline(metric.buffer, width=30)
                avg = metric.buffer.moving_average
                
                color = Colors.GREEN if avg < 75 else Colors.RED
                
                line = (
                    f"  {metric.name:<12} | "
                    f"{Colors.CYAN}{sparkline}{Colors.RESET} | "
                    f"Cur: {color}{metric.value:>6.1f} {metric.unit:<4}{Colors.RESET} | "
                    f"Avg (60s): {Colors.DIM}{avg:>6.1f} {metric.unit}{Colors.RESET}\n"
                )
                frame_buffer.append(line)
            frame_buffer.append("\n")

        frame_buffer.append(f"{Colors.DIM}Press Ctrl+C to trigger graceful shutdown.{Colors.RESET}\n")
        
        sys.stdout.write("".join(frame_buffer))
        sys.stdout.flush()

class TaskScheduler:
    def __init__(self, fps: int = 2):
        self.fps = fps
        self.delay = 1.0 / fps
        self.collectors: List[BaseCollector] = [cls() for cls in CollectorRegistry.registry]
        self.ui = TerminalRenderer()
        self.running = False

    async def _data_ingestion_loop(self) -> None:
        while self.running:
            for collector in self.collectors:
                collector.collect()
            await asyncio.sleep(self.delay)

    async def _ui_render_loop(self) -> None:
        while self.running:
            self.ui.render(self.collectors)
            await asyncio.sleep(self.delay)

    def _shutdown_handler(self, sig: Any, frame: Any) -> None:
        self.running = False

    async def start(self) -> None:
        self.running = True
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_running_loop().add_signal_handler(sig, functools.partial(self._shutdown_handler, sig, None))
            except NotImplementedError:
                signal.signal(sig, self._shutdown_handler)

        for collector in self.collectors:
            collector.collect()

        tasks = [
            asyncio.create_task(self._data_ingestion_loop()),
            asyncio.create_task(self._ui_render_loop())
        ]
        
        while self.running:
            await asyncio.sleep(0.1)

        for task in tasks:
            task.cancel()
        self.ui.cleanup()
        print("\nShutdown complete. Resources freed.")

def main() -> None:
    scheduler = TaskScheduler(fps=2)
    try:
        asyncio.run(scheduler.start())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()