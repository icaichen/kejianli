"""配置资源目录（rubric.zh.yaml 等）。加载见 keeplix.engines.scoring。"""

from pathlib import Path

CONFIG_DIR = Path(__file__).parent
RUBRIC_ZH = CONFIG_DIR / "rubric.zh.yaml"
