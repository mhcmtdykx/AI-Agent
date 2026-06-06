"""
可观测性系统 - 日志、追踪、监控
"""
import json
import os
import time
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from functools import wraps
from collections import defaultdict
import logging


class LogLevel:
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEntry:
    """日志条目"""
    def __init__(self, level: str, message: str, module: str = None, metadata: Dict = None):
        self.log_id = str(uuid.uuid4())[:8]
        self.level = level
        self.message = message
        self.module = module
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "log_id": self.log_id,
            "level": self.level,
            "message": self.message,
            "module": self.module,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


class TraceSpan:
    """追踪跨度"""
    def __init__(self, trace_id: str, span_id: str, name: str, parent_id: str = None):
        self.trace_id = trace_id
        self.span_id = span_id
        self.name = name
        self.parent_id = parent_id
        self.start_time = time.time()
        self.end_time = None
        self.duration = None
        self.status = "running"  # running, completed, error
        self.attributes: Dict[str, Any] = {}
        self.events: List[Dict] = []
    
    def set_attribute(self, key: str, value: Any):
        """设置属性"""
        self.attributes[key] = value
    
    def add_event(self, name: str, attributes: Dict = None):
        """添加事件"""
        self.events.append({
            "name": name,
            "attributes": attributes or {},
            "timestamp": datetime.now().isoformat()
        })
    
    def finish(self, status: str = "completed"):
        """完成跨度"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.status = status
    
    def to_dict(self) -> Dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events
        }


class Trace:
    """追踪"""
    def __init__(self, trace_id: str, name: str):
        self.trace_id = trace_id
        self.name = name
        self.spans: Dict[str, TraceSpan] = {}
        self.start_time = time.time()
        self.end_time = None
        self.duration = None
    
    def create_span(self, name: str, parent_id: str = None) -> TraceSpan:
        """创建跨度"""
        span_id = str(uuid.uuid4())[:8]
        span = TraceSpan(self.trace_id, span_id, name, parent_id)
        self.spans[span_id] = span
        return span
    
    def finish(self):
        """完成追踪"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
    
    def to_dict(self) -> Dict:
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "spans": {sid: span.to_dict() for sid, span in self.spans.items()}
        }


class MetricCollector:
    """指标收集器"""
    def __init__(self):
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
    
    def increment_counter(self, name: str, value: int = 1):
        """增加计数器"""
        self.counters[name] += value
    
    def set_gauge(self, name: str, value: float):
        """设置仪表盘值"""
        self.gauges[name] = value
    
    def record_histogram(self, name: str, value: float):
        """记录直方图值"""
        self.histograms[name].append(value)
    
    def get_metrics(self) -> Dict:
        """获取所有指标"""
        metrics = {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {}
        }
        
        # 计算直方图统计
        for name, values in self.histograms.items():
            if values:
                metrics["histograms"][name] = {
                    "count": len(values),
                    "sum": sum(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values)
                }
        
        return metrics
    
    def reset(self):
        """重置指标"""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()


class ObservabilitySystem:
    """可观测性系统"""
    
    def __init__(self, storage_path: str = "observability_storage", max_logs: int = 10000):
        """
        初始化可观测性系统
        
        Args:
            storage_path: 存储路径
            max_logs: 最大日志数量
        """
        self.storage_path = storage_path
        self.max_logs = max_logs
        
        # 日志
        self.logs: List[LogEntry] = []
        
        # 追踪
        self.traces: Dict[str, Trace] = {}
        self.active_traces: Dict[str, Trace] = {}
        
        # 指标
        self.metrics = MetricCollector()
        
        # 确保存储目录存在
        os.makedirs(storage_path, exist_ok=True)
        
        # 配置标准日志
        self._setup_logging()
    
    def _setup_logging(self):
        """配置标准日志"""
        self.logger = logging.getLogger("agent_observability")
        self.logger.setLevel(logging.DEBUG)
        
        # 控制台处理器
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log(self, level: str, message: str, module: str = None, metadata: Dict = None):
        """记录日志"""
        entry = LogEntry(level, message, module, metadata)
        self.logs.append(entry)
        
        # 限制日志数量
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
        
        # 同时输出到标准日志
        log_message = "[{}] {}".format(module or "general", message)
        if level == LogLevel.DEBUG:
            self.logger.debug(log_message)
        elif level == LogLevel.INFO:
            self.logger.info(log_message)
        elif level == LogLevel.WARNING:
            self.logger.warning(log_message)
        elif level == LogLevel.ERROR:
            self.logger.error(log_message)
        elif level == LogLevel.CRITICAL:
            self.logger.critical(log_message)
        
        # 更新指标
        self.metrics.increment_counter("logs.{}".format(level.lower()))
        
        return entry
    
    def debug(self, message: str, module: str = None, metadata: Dict = None):
        return self.log(LogLevel.DEBUG, message, module, metadata)
    
    def info(self, message: str, module: str = None, metadata: Dict = None):
        return self.log(LogLevel.INFO, message, module, metadata)
    
    def warning(self, message: str, module: str = None, metadata: Dict = None):
        return self.log(LogLevel.WARNING, message, module, metadata)
    
    def error(self, message: str, module: str = None, metadata: Dict = None):
        return self.log(LogLevel.ERROR, message, module, metadata)
    
    def critical(self, message: str, module: str = None, metadata: Dict = None):
        return self.log(LogLevel.CRITICAL, message, module, metadata)
    
    def start_trace(self, name: str) -> Trace:
        """开始追踪"""
        trace_id = str(uuid.uuid4())[:8]
        trace = Trace(trace_id, name)
        self.traces[trace_id] = trace
        self.active_traces[trace_id] = trace
        
        self.info("Trace started: {}".format(name), "tracer", {"trace_id": trace_id})
        self.metrics.increment_counter("traces.started")
        
        return trace
    
    def end_trace(self, trace_id: str):
        """结束追踪"""
        if trace_id in self.active_traces:
            trace = self.active_traces[trace_id]
            trace.finish()
            del self.active_traces[trace_id]
            
            self.info("Trace ended: {}".format(trace.name), "tracer", {
                "trace_id": trace_id,
                "duration": trace.duration
            })
            self.metrics.increment_counter("traces.completed")
            self.metrics.record_histogram("trace.duration", trace.duration)
    
    def create_span(self, trace_id: str, name: str, parent_id: str = None) -> Optional[TraceSpan]:
        """创建跨度"""
        if trace_id in self.traces:
            span = self.traces[trace_id].create_span(name, parent_id)
            self.metrics.increment_counter("spans.created")
            return span
        return None
    
    def get_logs(self, level: str = None, module: str = None, limit: int = 100) -> List[Dict]:
        """获取日志"""
        logs = self.logs
        
        if level:
            logs = [l for l in logs if l.level == level]
        if module:
            logs = [l for l in logs if l.module == module]
        
        return [l.to_dict() for l in logs[-limit:]]
    
    def get_traces(self, limit: int = 10) -> List[Dict]:
        """获取追踪"""
        traces = list(self.traces.values())
        return [t.to_dict() for t in traces[-limit:]]
    
    def get_trace(self, trace_id: str) -> Optional[Dict]:
        """获取单个追踪"""
        if trace_id in self.traces:
            return self.traces[trace_id].to_dict()
        return None
    
    def get_metrics(self) -> Dict:
        """获取指标"""
        return self.metrics.get_metrics()
    
    def get_system_health(self) -> Dict:
        """获取系统健康状态"""
        metrics = self.get_metrics()
        
        # 计算错误率
        total_logs = sum(metrics["counters"].get("logs.{}".format(level), 0) 
                        for level in ["debug", "info", "warning", "error", "critical"])
        error_logs = metrics["counters"].get("logs.error", 0) + metrics["counters"].get("logs.critical", 0)
        error_rate = (error_logs / total_logs * 100) if total_logs > 0 else 0
        
        # 计算平均追踪时间
        trace_durations = metrics["histograms"].get("trace.duration", {})
        avg_trace_duration = trace_durations.get("avg", 0) if trace_durations else 0
        
        health = {
            "status": "healthy" if error_rate < 5 else "degraded" if error_rate < 20 else "unhealthy",
            "error_rate": round(error_rate, 2),
            "average_trace_duration": round(avg_trace_duration, 3),
            "active_traces": len(self.active_traces),
            "total_logs": total_logs,
            "total_traces": metrics["counters"].get("traces.completed", 0)
        }
        
        return health
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_logs": len(self.logs),
            "total_traces": len(self.traces),
            "active_traces": len(self.active_traces),
            "metrics": self.get_metrics()
        }
    
    def clear(self):
        """清空数据"""
        self.logs.clear()
        self.traces.clear()
        self.active_traces.clear()
        self.metrics.reset()
    
    def export_logs(self, file_path: str = None) -> str:
        """导出日志"""
        if file_path is None:
            file_path = os.path.join(self.storage_path, "logs_export.json")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump([l.to_dict() for l in self.logs], f, ensure_ascii=False, indent=2)
        
        return file_path
    
    def export_traces(self, file_path: str = None) -> str:
        """导出追踪"""
        if file_path is None:
            file_path = os.path.join(self.storage_path, "traces_export.json")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump([t.to_dict() for t in self.traces.values()], f, ensure_ascii=False, indent=2)
        
        return file_path


def trace_function(name: str = None):
    """追踪装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = name or func.__name__
            obs = get_observability_system()
            
            # 创建追踪
            trace = obs.start_trace(func_name)
            span = trace.create_span(func_name)
            
            try:
                result = func(*args, **kwargs)
                span.set_attribute("success", True)
                return result
            except Exception as e:
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                obs.error("Error in {}: {}".format(func_name, str(e)), "tracer")
                raise
            finally:
                span.finish()
                obs.end_trace(trace.trace_id)
        
        return wrapper
    return decorator


def log_function(level: str = LogLevel.INFO, module: str = None):
    """日志装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            obs = get_observability_system()
            
            obs.log(level, "Calling {}".format(func_name), module)
            
            try:
                result = func(*args, **kwargs)
                obs.log(level, "{} completed successfully".format(func_name), module)
                return result
            except Exception as e:
                obs.error("Error in {}: {}".format(func_name, str(e)), module)
                raise
        
        return wrapper
    return decorator


# 全局可观测性系统
observability_system = ObservabilitySystem()

def get_observability_system() -> ObservabilitySystem:
    """获取可观测性系统"""
    return observability_system
