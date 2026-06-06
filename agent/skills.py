"""
Skills技能系统 - 配置驱动的模块化AI能力封装
支持从YAML/JSON配置文件动态加载技能
"""
import os
import json
import yaml
import importlib
import inspect
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class SkillParameter:
    """技能参数定义"""
    name: str
    type: str  # string, integer, float, boolean, array, object
    description: str
    required: bool = True
    default: Any = None
    
    def to_dict(self):
        return asdict(self)


@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str
    category: str  # general, search, code, data, communication
    execute_func: Callable
    parameters: List[SkillParameter]
    version: str = "1.0.0"
    author: str = "system"
    enabled: bool = True
    config_source: str = None  # 配置文件来源
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": [p.to_dict() for p in self.parameters],
            "version": self.version,
            "author": self.author,
            "enabled": self.enabled,
            "config_source": self.config_source
        }
    
    def to_openai_function(self):
        """转换为OpenAI Function Calling格式"""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description
            }
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


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
    
    def execute(self, skill_name: str, **kwargs) -> Any:
        """执行技能"""
        skill = self.get_skill(skill_name)
        if not skill:
            return {"error": "技能不存在: {}".format(skill_name)}
        
        if not skill.enabled:
            return {"error": "技能已禁用: {}".format(skill_name)}
        
        try:
            # 验证参数
            validated_args = self._validate_parameters(skill, kwargs)
            result = skill.execute_func(**validated_args)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _validate_parameters(self, skill: Skill, args: Dict) -> Dict:
        """验证参数"""
        validated = {}
        
        for param in skill.parameters:
            if param.name in args:
                value = args[param.name]
                # 简单类型验证
                if param.type == "integer":
                    validated[param.name] = int(value)
                elif param.type == "float" or param.type == "number":
                    validated[param.name] = float(value)
                elif param.type == "boolean":
                    validated[param.name] = bool(value)
                else:
                    validated[param.name] = value
            elif param.required:
                if param.default is not None:
                    validated[param.name] = param.default
                else:
                    raise ValueError("缺少必需参数: {}".format(param.name))
            elif param.default is not None:
                validated[param.name] = param.default
        
        return validated
    
    def get_tools_schema(self) -> List[Dict]:
        """获取所有技能的OpenAI工具模式"""
        return [skill.to_openai_function() for skill in self.skills.values() if skill.enabled]
    
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
        self.loaded_configs: Dict[str, Dict] = {}
    
    def load_from_directory(self, directory: str = None) -> List[Skill]:
        """从目录加载所有技能配置"""
        config_dir = directory or self.config_dir
        skills = []
        
        if not os.path.exists(config_dir):
            print(f"配置目录不存在: {config_dir}")
            return skills
        
        for filename in os.listdir(config_dir):
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
        
        return self._create_skill_from_config(config, filepath)
    
    def load_from_config(self, config: Dict) -> Optional[Skill]:
        """从配置字典创建技能"""
        return self._create_skill_from_config(config)
    
    def _create_skill_from_config(self, config: Dict, filepath: str = None) -> Optional[Skill]:
        """从配置创建技能对象"""
        name = config.get('name')
        if not name:
            raise ValueError("配置缺少name字段")
        
        # 解析参数
        parameters = []
        for param_config in config.get('parameters', []):
            param = SkillParameter(
                name=param_config['name'],
                type=param_config.get('type', 'string'),
                description=param_config.get('description', ''),
                required=param_config.get('required', True),
                default=param_config.get('default')
            )
            parameters.append(param)
        
        # 根据实现类型创建执行函数
        impl = config.get('implementation', {})
        execute_func = self._create_execute_function(impl, name)
        
        skill = Skill(
            name=name,
            description=config.get('description', ''),
            category=config.get('category', 'general'),
            execute_func=execute_func,
            parameters=parameters,
            version=config.get('version', '1.0.0'),
            author=config.get('author', 'system'),
            config_source=filepath
        )
        
        self.loaded_configs[name] = config
        return skill
    
    def _create_execute_function(self, impl: Dict, skill_name: str) -> Callable:
        """根据实现配置创建执行函数"""
        impl_type = impl.get('type', 'script')
        
        if impl_type == 'script':
            return self._create_script_function(impl)
        elif impl_type == 'api':
            return self._create_api_function(impl)
        elif impl_type == 'llm':
            return self._create_llm_function(impl)
        else:
            raise ValueError(f"不支持的实现类型: {impl_type}")
    
    def _create_script_function(self, impl: Dict) -> Callable:
        """创建脚本类型的执行函数"""
        code = impl.get('code', '')
        language = impl.get('language', 'python')
        
        if language != 'python':
            raise ValueError(f"目前只支持Python脚本: {language}")
        
        # 动态执行Python代码
        namespace = {}
        exec(code, namespace)
        
        if 'execute' not in namespace:
            raise ValueError("脚本必须定义execute函数")
        
        return namespace['execute']
    
    def _create_api_function(self, impl: Dict) -> Callable:
        """创建API类型的执行函数"""
        import requests
        
        endpoint = impl.get('endpoint', '')
        method = impl.get('method', 'POST').upper()
        headers = impl.get('headers', {})
        body_template = impl.get('body_template', '{}')
        response_path = impl.get('response_path', '')
        
        # 检查是否有备用实现
        fallback = impl.get('fallback')
        fallback_func = None
        if fallback:
            fallback_func = self._create_script_function(fallback)
        
        def execute(**kwargs):
            try:
                # 渲染请求体模板
                body_str = body_template
                for key, value in kwargs.items():
                    body_str = body_str.replace('{{' + key + '}}', str(value))
                
                body = json.loads(body_str)
                
                # 发送请求
                if method == 'GET':
                    response = requests.get(endpoint, headers=headers, params=body, timeout=10)
                else:
                    response = requests.post(endpoint, headers=headers, json=body, timeout=10)
                
                response.raise_for_status()
                result = response.json()
                
                # 提取响应数据
                if response_path:
                    for key in response_path.split('.'):
                        result = result.get(key, {})
                
                return result
            except Exception as e:
                # 使用备用实现
                if fallback_func:
                    return fallback_func(**kwargs)
                return f"API调用失败: {str(e)}"
        
        return execute
    
    def _create_llm_function(self, impl: Dict) -> Callable:
        """创建LLM类型的执行函数"""
        prompt_template = impl.get('prompt_template', '')
        
        def execute(**kwargs):
            # 渲染提示模板
            prompt = prompt_template
            for key, value in kwargs.items():
                prompt = prompt.replace('{{' + key + '}}', str(value))
            
            # 这里应该调用LLM API
            # 简化实现：返回提示内容
            return f"[LLM处理] {prompt}"
        
        return execute


# ========== 内置技能（兼容旧版本） ==========

def get_current_time() -> str:
    """获取当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 创建全局技能注册表
skill_registry = SkillRegistry()
config_loader = ConfigSkillLoader()

def register_default_skills():
    """注册默认技能（从配置文件加载）"""
    skills = config_loader.load_from_directory()
    for skill in skills:
        skill_registry.register(skill)
    
    # 如果没有配置文件，注册内置技能
    if not skills:
        _register_builtin_skills()

def _register_builtin_skills():
    """注册内置技能（备用）"""
    builtin_skills = [
        Skill(
            name="get_current_time",
            description="获取当前时间",
            category="general",
            execute_func=get_current_time,
            parameters=[]
        ),
        Skill(
            name="calculator",
            description="计算数学表达式",
            category="data",
            execute_func=lambda expression: str(eval(expression, {"__builtins__": {}, "sqrt": __import__('math').sqrt})),
            parameters=[
                SkillParameter("expression", "string", "数学表达式")
            ]
        )
    ]
    
    for skill in builtin_skills:
        skill_registry.register(skill)

# 注册技能
register_default_skills()


def get_skill_registry() -> SkillRegistry:
    """获取技能注册表"""
    return skill_registry

def get_config_loader() -> ConfigSkillLoader:
    """获取配置加载器"""
    return config_loader

def reload_skills():
    """重新加载所有技能"""
    skill_registry.skills.clear()
    skill_registry.categories.clear()
    register_default_skills()
