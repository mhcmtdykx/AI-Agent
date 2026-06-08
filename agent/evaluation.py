"""
评估指标系统 - 用于评估Agent性能
"""
import json
import os
import time
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict


class MetricRecord:
    """指标记录"""
    def __init__(self, metric_name: str, value: float, metadata: Dict = None):
        self.metric_name = metric_name
        self.value = value
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


class ConversationRecord:
    """对话记录"""
    def __init__(self, session_id: str, user_message: str, ai_response: str, **kwargs):
        self.session_id = session_id
        self.user_message = user_message
        self.ai_response = ai_response
        self.timestamp = kwargs.get('timestamp', datetime.now().isoformat())
        self.latency = kwargs.get('latency', 0)  # 响应延迟（秒）
        self.token_count = kwargs.get('token_count', 0)  # token数量
        self.tool_calls = kwargs.get('tool_calls', [])  # 工具调用
        self.success = kwargs.get('success', True)  # 是否成功
        self.error_message = kwargs.get('error_message', None)  # 错误信息
        self.user_rating = kwargs.get('user_rating', None)  # 用户评分 (1-5)
        self.feedback = kwargs.get('feedback', None)  # 用户反馈
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "user_message": self.user_message,
            "ai_response": self.ai_response,
            "timestamp": self.timestamp,
            "latency": self.latency,
            "token_count": self.token_count,
            "tool_calls": self.tool_calls,
            "success": self.success,
            "error_message": self.error_message,
            "user_rating": self.user_rating,
            "feedback": self.feedback
        }


class EvaluationSystem:
    """评估系统"""
    
    def __init__(self, storage_path: str = "evaluation_storage"):
        """
        初始化评估系统
        
        Args:
            storage_path: 存储路径
        """
        self.storage_path = storage_path
        self.metrics: List[MetricRecord] = []
        self.conversations: List[ConversationRecord] = []
        
        # 统计数据
        self.stats = {
            "total_conversations": 0,
            "successful_conversations": 0,
            "failed_conversations": 0,
            "average_latency": 0,
            "total_tokens": 0,
            "tool_usage": defaultdict(int),
            "user_ratings": [],
            "hourly_distribution": defaultdict(int),
            "daily_distribution": defaultdict(int)
        }
        
        # 确保存储目录存在
        os.makedirs(storage_path, exist_ok=True)
        
        # 加载历史数据
        self._load_data()
    
    def _get_conversations_file(self) -> str:
        return os.path.join(self.storage_path, "conversations.json")
    
    def _get_metrics_file(self) -> str:
        return os.path.join(self.storage_path, "metrics.json")
    
    def _load_data(self):
        """加载数据"""
        # 加载对话记录
        conv_file = self._get_conversations_file()
        if os.path.exists(conv_file):
            try:
                with open(conv_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.conversations = [ConversationRecord(**item) for item in data]
                    self._update_stats()
            except Exception as e:
                print(f"加载对话记录失败: {e}")
        
        # 加载指标记录
        metrics_file = self._get_metrics_file()
        if os.path.exists(metrics_file):
            try:
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.metrics = [MetricRecord(**item) for item in data]
            except Exception as e:
                print(f"加载指标记录失败: {e}")
    
    def _save_data(self):
        """保存数据"""
        # 保存对话记录
        conv_file = self._get_conversations_file()
        try:
            with open(conv_file, 'w', encoding='utf-8') as f:
                json.dump([c.to_dict() for c in self.conversations], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存对话记录失败: {e}")
        
        # 保存指标记录
        metrics_file = self._get_metrics_file()
        try:
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump([m.to_dict() for m in self.metrics], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存指标记录失败: {e}")
    
    def _update_stats(self):
        """更新统计数据"""
        self.stats["total_conversations"] = len(self.conversations)
        self.stats["successful_conversations"] = sum(1 for c in self.conversations if c.success)
        self.stats["failed_conversations"] = sum(1 for c in self.conversations if not c.success)
        
        # 计算平均延迟
        latencies = [c.latency for c in self.conversations if c.latency > 0]
        self.stats["average_latency"] = sum(latencies) / len(latencies) if latencies else 0
        
        # 统计token使用
        self.stats["total_tokens"] = sum(c.token_count for c in self.conversations)
        
        # 统计工具使用
        self.stats["tool_usage"] = defaultdict(int)
        for conv in self.conversations:
            for tool in conv.tool_calls:
                self.stats["tool_usage"][tool] += 1
        
        # 统计用户评分
        self.stats["user_ratings"] = [c.user_rating for c in self.conversations if c.user_rating]
        
        # 统计时间分布
        self.stats["hourly_distribution"] = defaultdict(int)
        self.stats["daily_distribution"] = defaultdict(int)
        for conv in self.conversations:
            try:
                dt = datetime.fromisoformat(conv.timestamp)
                self.stats["hourly_distribution"][dt.hour] += 1
                self.stats["daily_distribution"][dt.strftime("%Y-%m-%d")] += 1
            except:
                pass
    
    def record_conversation(self, session_id: str, user_message: str, ai_response: str, 
                          latency: float = 0, token_count: int = 0, 
                          tool_calls: List[str] = None, success: bool = True,
                          error_message: str = None) -> ConversationRecord:
        """记录对话"""
        record = ConversationRecord(session_id, user_message, ai_response)
        record.latency = latency
        record.token_count = token_count
        record.tool_calls = tool_calls or []
        record.success = success
        record.error_message = error_message
        
        self.conversations.append(record)
        self._update_stats()
        self._save_data()
        
        return record
    
    def record_metric(self, metric_name: str, value: float, metadata: Dict = None):
        """记录指标"""
        record = MetricRecord(metric_name, value, metadata)
        self.metrics.append(record)
        self._save_data()
    
    def rate_conversation(self, session_id: str, rating: int, feedback: str = None):
        """为对话评分"""
        for conv in self.conversations:
            if conv.session_id == session_id:
                conv.user_rating = max(1, min(5, rating))
                conv.feedback = feedback
                self._update_stats()
                self._save_data()
                return True
        return False
    
    def get_stats(self) -> Dict:
        """获取统计数据"""
        stats = self.stats.copy()
        
        # 计算成功率
        total = stats["total_conversations"]
        if total > 0:
            stats["success_rate"] = round(stats["successful_conversations"] / total * 100, 2)
        else:
            stats["success_rate"] = 0
        
        # 计算平均评分
        ratings = stats["user_ratings"]
        if ratings:
            stats["average_rating"] = round(sum(ratings) / len(ratings), 2)
            stats["rating_distribution"] = {
                i: ratings.count(i) for i in range(1, 6)
            }
        else:
            stats["average_rating"] = 0
            stats["rating_distribution"] = {}
        
        # 转换defaultdict为普通dict
        stats["tool_usage"] = dict(stats["tool_usage"])
        stats["hourly_distribution"] = dict(stats["hourly_distribution"])
        stats["daily_distribution"] = dict(stats["daily_distribution"])
        
        return stats
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """获取最近的对话"""
        return [c.to_dict() for c in self.conversations[-limit:]]
    
    def get_conversation_by_session(self, session_id: str) -> List[Dict]:
        """获取指定会话的对话"""
        return [c.to_dict() for c in self.conversations if c.session_id == session_id]
    
    def get_failed_conversations(self, limit: int = 10) -> List[Dict]:
        """获取失败的对话"""
        failed = [c for c in self.conversations if not c.success]
        return [c.to_dict() for c in failed[-limit:]]
    
    def get_tool_usage_stats(self) -> Dict:
        """获取工具使用统计"""
        return dict(self.stats["tool_usage"])
    
    def get_performance_report(self) -> Dict:
        """获取性能报告"""
        stats = self.get_stats()
        
        report = {
            "summary": {
                "total_conversations": stats["total_conversations"],
                "success_rate": stats["success_rate"],
                "average_latency": round(stats["average_latency"], 3),
                "average_rating": stats["average_rating"]
            },
            "tool_usage": stats["tool_usage"],
            "rating_distribution": stats["rating_distribution"],
            "recommendations": []
        }
        
        # 生成建议
        if stats["success_rate"] < 90:
            report["recommendations"].append("成功率较低，建议检查错误处理逻辑")
        
        if stats["average_latency"] > 5:
            report["recommendations"].append("响应延迟较高，建议优化API调用或缓存机制")
        
        if stats["average_rating"] < 4 and stats["user_ratings"]:
            report["recommendations"].append("用户满意度较低，建议改进回答质量")
        
        return report
    
    def clear(self):
        """清空数据"""
        self.conversations.clear()
        self.metrics.clear()
        self.stats = {
            "total_conversations": 0,
            "successful_conversations": 0,
            "failed_conversations": 0,
            "average_latency": 0,
            "total_tokens": 0,
            "tool_usage": defaultdict(int),
            "user_ratings": [],
            "hourly_distribution": defaultdict(int),
            "daily_distribution": defaultdict(int)
        }
        self._save_data()


# 全局评估系统
evaluation_system = EvaluationSystem()

def get_evaluation_system() -> EvaluationSystem:
    """获取评估系统"""
    return evaluation_system
