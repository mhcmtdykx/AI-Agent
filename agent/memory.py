"""
长期记忆系统 - 基于向量数据库的对话历史存储和检索
"""
import json
import os
import re
import math
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from collections import Counter


class MemoryEntry:
    """记忆条目"""
    def __init__(self, content: str, metadata: Dict = None):
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
        self.embedding = None  # 向量表示
    
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


class SimpleVectorIndex:
    """简单的向量索引（基于TF-IDF）"""
    
    def __init__(self):
        self.documents: List[str] = []
        self.idf_scores: Dict[str, float] = {}
        self.doc_vectors: List[Dict[str, float]] = []
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        tokens = []
        # 中文字符
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.extend(chinese_chars)
        # 英文单词
        english_words = re.findall(r'[a-zA-Z]+', text.lower())
        tokens.extend(english_words)
        return tokens
    
    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """计算词频"""
        counter = Counter(tokens)
        total = len(tokens)
        return {word: count / total for word, count in counter.items()}
    
    def _compute_idf(self):
        """计算逆文档频率"""
        doc_count = len(self.documents)
        word_doc_count = Counter()
        
        for doc in self.documents:
            tokens = set(self._tokenize(doc))
            for token in tokens:
                word_doc_count[token] += 1
        
        self.idf_scores = {
            word: math.log(doc_count / (count + 1)) + 1
            for word, count in word_doc_count.items()
        }
    
    def add(self, text: str):
        """添加文档"""
        self.documents.append(text)
        self._compute_idf()
        
        # 计算TF-IDF向量
        tokens = self._tokenize(text)
        tf = self._compute_tf(tokens)
        vector = {
            word: tf_val * self.idf_scores.get(word, 1.0)
            for word, tf_val in tf.items()
        }
        self.doc_vectors.append(vector)
    
    def search(self, query: str, top_k: int = 3) -> List[Tuple[int, float]]:
        """搜索相似文档，返回 (index, score) 列表"""
        if not self.documents:
            return []
        
        # 计算查询向量
        query_tokens = self._tokenize(query)
        query_tf = self._compute_tf(query_tokens)
        query_vector = {
            word: tf_val * self.idf_scores.get(word, 1.0)
            for word, tf_val in query_tf.items()
        }
        
        # 计算余弦相似度
        similarities = []
        for doc_vector in self.doc_vectors:
            similarity = self._cosine_similarity(query_vector, doc_vector)
            similarities.append(similarity)
        
        # 排序
        indexed_similarities = list(enumerate(similarities))
        indexed_similarities.sort(key=lambda x: x[1], reverse=True)
        
        return [(idx, score) for idx, score in indexed_similarities[:top_k] if score > 0]
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """计算余弦相似度"""
        common_words = set(vec1.keys()) & set(vec2.keys())
        if not common_words:
            return 0.0
        
        dot_product = sum(vec1[word] * vec2[word] for word in common_words)
        norm1 = math.sqrt(sum(val ** 2 for val in vec1.values()))
        norm2 = math.sqrt(sum(val ** 2 for val in vec2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def clear(self):
        """清空索引"""
        self.documents.clear()
        self.doc_vectors.clear()
        self.idf_scores.clear()


class LongTermMemory:
    """长期记忆系统"""
    
    def __init__(self, storage_path: str = "memory_storage"):
        """
        初始化长期记忆系统
        
        Args:
            storage_path: 存储路径
        """
        self.storage_path = storage_path
        self.memories: List[MemoryEntry] = []
        self.index = SimpleVectorIndex()
        
        # 确保存储目录存在
        os.makedirs(storage_path, exist_ok=True)
        
        # 加载已有记忆
        self._load_memories()
    
    def _get_storage_file(self) -> str:
        """获取存储文件路径"""
        return os.path.join(self.storage_path, "memories.json")
    
    def _load_memories(self):
        """加载记忆"""
        file_path = self._get_storage_file()
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.memories = [MemoryEntry.from_dict(item) for item in data]
                    # 重建索引
                    for memory in self.memories:
                        self.index.add(memory.content)
            except Exception as e:
                print("加载记忆失败: {}".format(e))
    
    def _save_memories(self):
        """保存记忆"""
        file_path = self._get_storage_file()
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([m.to_dict() for m in self.memories], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("保存记忆失败: {}".format(e))
    
    def add_memory(self, content: str, metadata: Dict = None) -> MemoryEntry:
        """添加记忆"""
        entry = MemoryEntry(content, metadata)
        self.memories.append(entry)
        self.index.add(content)
        self._save_memories()
        return entry
    
    def add_conversation(self, user_message: str, ai_response: str, session_id: str = None):
        """添加对话记忆"""
        # 存储用户消息
        self.add_memory(user_message, {
            "type": "user_message",
            "session_id": session_id,
            "role": "user"
        })
        
        # 存储AI回复
        self.add_memory(ai_response, {
            "type": "ai_response",
            "session_id": session_id,
            "role": "assistant",
            "in_response_to": user_message[:100]
        })
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[MemoryEntry, float]]:
        """搜索相关记忆"""
        results = self.index.search(query, top_k)
        return [(self.memories[idx], score) for idx, score in results]
    
    def get_context(self, query: str, top_k: int = 3) -> str:
        """获取相关上下文"""
        results = self.search(query, top_k)
        if not results:
            return ""
        
        context_parts = []
        for memory, score in results:
            context_parts.append(memory.content)
        
        return "\n\n".join(context_parts)
    
    def get_recent_memories(self, limit: int = 10) -> List[Dict]:
        """获取最近的记忆"""
        return [m.to_dict() for m in self.memories[-limit:]]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_memories": len(self.memories),
            "storage_path": self.storage_path
        }
    
    def clear(self):
        """清空记忆"""
        self.memories.clear()
        self.index.clear()
        self._save_memories()
    
    def export_memories(self) -> List[Dict]:
        """导出记忆"""
        return [m.to_dict() for m in self.memories]
    
    def import_memories(self, memories_data: List[Dict]):
        """导入记忆"""
        for data in memories_data:
            entry = MemoryEntry.from_dict(data)
            self.memories.append(entry)
            self.index.add(entry.content)
        self._save_memories()


class MemoryEnhancedAgent:
    """增强记忆的Agent"""
    
    def __init__(self, agent, memory_system: LongTermMemory = None):
        """
        初始化
        
        Args:
            agent: 基础Agent
            memory_system: 长期记忆系统
        """
        self.agent = agent
        self.memory = memory_system or LongTermMemory()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def chat(self, message: str) -> str:
        """带长期记忆的对话"""
        # 1. 搜索相关历史记忆
        relevant_context = self.memory.get_context(message, top_k=3)
        
        # 2. 如果有相关记忆，增强消息
        if relevant_context:
            enhanced_message = """请参考以下历史对话记录回答当前问题：

历史相关记录：
{context}

当前问题：{question}""".format(context=relevant_context, question=message)
        else:
            enhanced_message = message
        
        # 3. 调用原始Agent
        response = self.agent.chat(enhanced_message)
        
        # 4. 存储对话到长期记忆
        self.memory.add_conversation(message, response, self.session_id)
        
        return response
    
    def chat_stream(self, message: str):
        """流式对话"""
        # 搜索相关历史记忆
        relevant_context = self.memory.get_context(message, top_k=3)
        
        if relevant_context:
            enhanced_message = """请参考以下历史对话记录回答当前问题：

历史相关记录：
{context}

当前问题：{question}""".format(context=relevant_context, question=message)
        else:
            enhanced_message = message
        
        # 收集完整回复
        full_response = ""
        for item in self.agent.chat_stream(enhanced_message):
            yield item
            if item.get("content"):
                full_response += item["content"]
        
        # 存储对话到长期记忆
        if full_response:
            self.memory.add_conversation(message, full_response, self.session_id)
    
    def get_memory_stats(self) -> Dict:
        """获取记忆统计"""
        return self.memory.get_stats()
    
    def search_memory(self, query: str) -> List[Dict]:
        """搜索记忆"""
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
        """清空记忆"""
        self.memory.clear()


# 全局记忆系统
long_term_memory = LongTermMemory()

def get_long_term_memory() -> LongTermMemory:
    """获取长期记忆系统"""
    return long_term_memory
