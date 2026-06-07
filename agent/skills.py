"""
Skills技能系统 - LLM驱动的能力编排层

架构：
  Tools层（MCP）= 原子操作（calculator, web_search, text_analyzer...）
  Skills层      = 能力编排（prompt模板 + 工具依赖 + 工作流）

一个Skill不是直接执行代码，而是为LLM提供专业化的提示词和工具组合，
让LLM自主编排多个工具来完成复杂任务。
"""
import os
import json
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class WorkflowStep:
    """工作流步骤"""
    name: str              # 步骤名称
    description: str       # 步骤描述
    tool: str = ""         # 使用的工具名（可选，空表示LLM推理）
    prompt: str = ""       # 步骤提示词

    def to_dict(self):
        return asdict(self)


@dataclass
class Skill:
    """技能定义 - LLM驱动的能力编排"""
    name: str
    description: str
    category: str
    system_prompt: str                        # 给LLM的专业化提示词
    required_tools: List[str] = field(default_factory=list)  # 依赖的MCP工具
    workflow: List[WorkflowStep] = field(default_factory=list)  # 可选工作流
    examples: List[Dict] = field(default_factory=list)  # 示例输入输出
    version: str = "1.0.0"
    author: str = "system"
    enabled: bool = True
    config_source: str = None

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "system_prompt": self.system_prompt[:200] + "..." if len(self.system_prompt) > 200 else self.system_prompt,
            "required_tools": self.required_tools,
            "workflow": [s.to_dict() for s in self.workflow],
            "examples": self.examples[:2],
            "version": self.version,
            "author": self.author,
            "enabled": self.enabled,
            "config_source": self.config_source,
        }

    def get_full_prompt(self, available_tools_desc: str = "") -> str:
        """生成完整的技能提示词（system_prompt + 工具描述 + 工作流）"""
        parts = [self.system_prompt]

        if self.required_tools and available_tools_desc:
            parts.append(f"\n可用工具:\n{available_tools_desc}")

        if self.workflow:
            parts.append("\n工作流程:")
            for i, step in enumerate(self.workflow, 1):
                tool_hint = f" (使用 {step.tool})" if step.tool else " (LLM推理)"
                parts.append(f"  {i}. {step.name}{tool_hint}: {step.description}")
                if step.prompt:
                    parts.append(f"     提示: {step.prompt}")

        if self.examples:
            parts.append("\n示例:")
            for ex in self.examples[:2]:
                parts.append(f"  输入: {ex.get('input', '')}")
                parts.append(f"  输出: {ex.get('output', '')}")

        return "\n".join(parts)


class SkillRegistry:
    """技能注册表"""

    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.categories: Dict[str, List[str]] = {}

    def register(self, skill: Skill):
        """注册技能"""
        self.skills[skill.name] = skill
        if skill.category not in self.categories:
            self.categories[skill.category] = []
        if skill.name not in self.categories[skill.category]:
            self.categories[skill.category].append(skill.name)

    def unregister(self, skill_name: str):
        """注销技能"""
        if skill_name in self.skills:
            skill = self.skills[skill_name]
            if skill.category in self.categories:
                self.categories[skill.category].remove(skill_name)
            del self.skills[skill_name]

    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """获取技能"""
        return self.skills.get(skill_name)

    def list_skills(self, category: str = None, enabled_only: bool = True) -> List[Dict]:
        """列出技能"""
        skills = []
        for name, skill in self.skills.items():
            if enabled_only and not skill.enabled:
                continue
            if category and skill.category != category:
                continue
            skills.append(skill.to_dict())
        return skills

    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self.categories.keys())

    def get_tools_schema(self) -> List[Dict]:
        """获取技能的OpenAI工具模式（每个技能作为一个可调用工具）"""
        schemas = []
        for skill in self.skills.values():
            if not skill.enabled:
                continue
            # 每个Skill本身作为一个function calling工具
            # 参数是用户输入的自然语言任务描述
            schemas.append({
                "type": "function",
                "function": {
                    "name": f"skill_{skill.name}",
                    "description": f"[技能] {skill.description}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "任务描述或用户输入"
                            }
                        },
                        "required": ["task"]
                    }
                }
            })
        return schemas

    def enable_skill(self, skill_name: str):
        """启用技能"""
        if skill_name in self.skills:
            self.skills[skill_name].enabled = True

    def disable_skill(self, skill_name: str):
        """禁用技能"""
        if skill_name in self.skills:
            self.skills[skill_name].enabled = False


class ConfigSkillLoader:
    """配置驱动的技能加载器"""

    def __init__(self, config_dir: str = "skills_config"):
        self.config_dir = config_dir

    def load_from_directory(self, directory: str = None) -> List[Skill]:
        """从目录加载所有技能配置"""
        config_dir = directory or self.config_dir
        skills = []

        if not os.path.exists(config_dir):
            print(f"技能配置目录不存在: {config_dir}")
            return skills

        for filename in sorted(os.listdir(config_dir)):
            if filename.endswith(('.yaml', '.yml', '.json')):
                filepath = os.path.join(config_dir, filename)
                try:
                    skill = self.load_from_file(filepath)
                    if skill:
                        skills.append(skill)
                except Exception as e:
                    print(f"加载技能配置失败 {filename}: {e}")

        return skills

    def load_from_file(self, filepath: str) -> Optional[Skill]:
        """从文件加载单个技能配置"""
        with open(filepath, 'r', encoding='utf-8') as f:
            if filepath.endswith('.json'):
                config = json.load(f)
            else:
                config = yaml.safe_load(f)

        if not config:
            return None

        return self._create_skill_from_config(config, filepath)

    def _create_skill_from_config(self, config: Dict, filepath: str = None) -> Optional[Skill]:
        """从配置创建技能对象"""
        name = config.get('name')
        if not name:
            raise ValueError("配置缺少name字段")

        # 解析工作流步骤
        workflow = []
        for step_config in config.get('workflow', []):
            step = WorkflowStep(
                name=step_config.get('name', ''),
                description=step_config.get('description', ''),
                tool=step_config.get('tool', ''),
                prompt=step_config.get('prompt', ''),
            )
            workflow.append(step)

        # 解析示例
        examples = config.get('examples', [])

        skill = Skill(
            name=name,
            description=config.get('description', ''),
            category=config.get('category', 'general'),
            system_prompt=config.get('system_prompt', config.get('description', '')),
            required_tools=config.get('required_tools', []),
            workflow=workflow,
            examples=examples,
            version=config.get('version', '1.0.0'),
            author=config.get('author', 'system'),
            config_source=filepath,
        )

        return skill


# ========== 全局实例 ==========
skill_registry = SkillRegistry()
config_loader = ConfigSkillLoader()


def register_default_skills():
    """注册默认技能（从配置文件加载）"""
    skills = config_loader.load_from_directory()
    for skill in skills:
        skill_registry.register(skill)
    print(f"已加载 {len(skills)} 个技能: {[s.name for s in skills]}")


# 模块加载时自动注册技能
register_default_skills()


def reload_skills():
    """重新加载技能"""
    skill_registry.skills.clear()
    skill_registry.categories.clear()
    register_default_skills()


def get_skill_registry() -> SkillRegistry:
    """获取全局技能注册表"""
    return skill_registry


def get_config_loader() -> ConfigSkillLoader:
    """获取配置加载器"""
    return config_loader
