"""
长期记忆系统 - 基于向量数据库的对话历史存储和检索
"""
import json
import os
from typing import List, Dict, Tuple
from datetime import datetime

from .vector_store import TFIDFIndex


class MemoryEntry:
    """记忆条目"""
    def __init__(self, content: str, metadata: Dict = None):
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryEntry':
        entry = cls(data["content"], data.get("metadata", {}))
        entry.timestamp = data.get("timestamp", datetime.now().isoformat())
        return entry


class LongTermMemory:
    """长期记忆系统"""

    def __init__(self, storage_path: str = "memory_storage"):
        self.storage_path = storage_path
        self.memories: List[MemoryEntry] = []
        self._index = TFIDFIndex()

        os.makedirs(storage_path, exist_ok=True)
        self._load_memories()

    def _get_storage_file(self) -> str:
        return os.path.join(self.storage_path, "memories.json")

    def _load_memories(self):
        """加载记忆"""
        file_path = self._get_storage_file()
        if not os.path.exists(file_path):
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.memories = [MemoryEntry.from_dict(item) for item in data]
            # 批量重建索引（比逐条 add 性能更好）
            if self.memories:
                self._index.add_batch([m.content for m in self.memories])
        except Exception as e:
            print(f"加载记忆失败: {e}")

    def _save_memories(self):
        """保存记忆"""
        file_path = self._get_storage_file()
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([m.to_dict() for m in self.memories], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存记忆失败: {e}")

    def add_memory(self, content: str, metadata: Dict = None) -> MemoryEntry:
        """添加记忆"""
        entry = MemoryEntry(content, metadata)
        self.memories.append(entry)
        self._index.add(content)
        self._save_memories()
        return entry

    def add_conversation(self, user_message: str, ai_response: str, session_id: str = None):
        """添加对话记忆"""
        self.add_memory(user_message, {
            "type": "user_message",
            "session_id": session_id,
            "role": "user"
        })
        self.add_memory(ai_response, {
            "type": "ai_response",
            "session_id": session_id,
            "role": "assistant",
            "in_response_to": user_message[:100]
        })

    def search(self, query: str, top_k: int = 5) -> List[Tuple[MemoryEntry, float]]:
        """搜索相关记忆"""
        results = self._index.search(query, top_k)
        return [(self.memories[idx], score) for idx, score in results]

    def get_context(self, query: str, top_k: int = 3) -> str:
        """获取相关上下文"""
        results = self.search(query, top_k)
        if not results:
            return ""
        return "\n\n".join(memory.content for memory, _ in results)

    def get_recent_memories(self, limit: int = 10) -> List[Dict]:
        return [m.to_dict() for m in self.memories[-limit:]]

    def get_stats(self) -> Dict:
        return {
            "total_memories": len(self.memories),
            "storage_path": self.storage_path
        }

    def clear(self):
        self.memories.clear()
        self._index.clear()
        self._save_memories()

    def export_memories(self) -> List[Dict]:
        return [m.to_dict() for m in self.memories]

    def import_memories(self, memories_data: List[Dict]):
        texts = []
        for data in memories_data:
            entry = MemoryEntry.from_dict(data)
            self.memories.append(entry)
            texts.append(entry.content)
        if texts:
            self._index.add_batch(texts)
        self._save_memories()


class MemoryEnhancedAgent:
    """增强记忆的Agent"""

    def __init__(self, agent, memory_system: LongTermMemory = None):
        self.agent = agent
        self.memory = memory_system or LongTermMemory()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def chat(self, message: str) -> str:
        """带长期记忆的对话"""
        relevant_context = self.memory.get_context(message, top_k=3)

        if relevant_context:
            enhanced_message = (
                "请参考以下历史对话记录回答当前问题：\n\n"
                f"历史相关记录：\n{relevant_context}\n\n"
                f"当前问题：{message}"
            )
        else:
            enhanced_message = message

        response = self.agent.chat(enhanced_message)
        self.memory.add_conversation(message, response, self.session_id)
        return response

    def chat_stream(self, message: str):
        """流式对话"""
        relevant_context = self.memory.get_context(message, top_k=3)

        if relevant_context:
            enhanced_message = (
                "请参考以下历史对话记录回答当前问题：\n\n"
                f"历史相关记录：\n{relevant_context}\n\n"
                f"当前问题：{message}"
            )
        else:
            enhanced_message = message

        full_response = ""
        for item in self.agent.chat_stream(enhanced_message):
            yield item
            if item.get("content"):
                full_response += item["content"]

        if full_response:
            self.memory.add_conversation(message, full_response, self.session_id)

    def get_memory_stats(self) -> Dict:
        return self.memory.get_stats()

    def search_memory(self, query: str) -> List[Dict]:
        results = self.memory.search(query)
        return [
            {
                "content": entry.content,
                "metadata": entry.metadata,
                "timestamp": entry.timestamp,
                "score": round(score, 4)
            }
            for entry, score in results
        ]

    def clear_memory(self):
        self.memory.clear()


# 全局记忆系统
_memory_instances = {}


def get_long_term_memory(user_id: str = None) -> LongTermMemory:
    if user_id:
        if user_id not in _memory_instances:
            storage_path = os.path.join("user_storage", "data", user_id, "memory_storage")
            _memory_instances[user_id] = LongTermMemory(storage_path=storage_path)
        return _memory_instances[user_id]
    # 无 user_id 时返回全局实例（向后兼容）
    if "_global" not in _memory_instances:
        _memory_instances["_global"] = LongTermMemory()
    return _memory_instances["_global"]
