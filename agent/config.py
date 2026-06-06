"""
配置管理模块
"""
import os


class Config:
    """Agent配置类"""

    def __init__(
        self,
        api_key=None,
        base_url=None,
        model_name=None,
        temperature=None,
        max_iterations=None,
        verbose=None,
    ):
        # OpenAI API配置
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")

        # 模型配置
        self.model_name = model_name or os.getenv("MODEL_NAME", "gpt-3.5-turbo")
        self.temperature = temperature if temperature is not None else float(os.getenv("TEMPERATURE", "0.7"))
        self.max_iterations = max_iterations if max_iterations is not None else int(os.getenv("MAX_ITERATIONS", "5"))

        # 日志配置
        self.verbose = verbose if verbose is not None else os.getenv("VERBOSE", "false").lower() == "true"

    def validate(self):
        """验证配置"""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 未设置。请通过环境变量或配置文件设置。")
        if self.temperature < 0 or self.temperature > 2:
            raise ValueError("temperature 必须在 0 到 2 之间")
        if self.max_iterations < 1:
            raise ValueError("max_iterations 必须大于 0")
        return True

    @classmethod
    def from_env(cls):
        """从环境变量创建配置"""
        return cls()

    def __repr__(self):
        return "Config(model={}, temperature={}, base_url={})".format(
            self.model_name,
            self.temperature,
            "***" if self.base_url else "None",
        )
