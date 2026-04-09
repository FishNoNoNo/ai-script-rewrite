import logging

from openai import APITimeoutError, AsyncOpenAI, APIConnectionError
from config.settings import OpenaiConfig, app_config
import asyncio

logging.getLogger("openai").setLevel(logging.WARNING)


class OpenaiApi:
    def __init__(self, config: OpenaiConfig):
        self.api_key = config.api_key
        self.base_url = config.base_url
        self.model = config.model

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def chat(self, prompt: str, text: str, **kwargs) -> str:
        try:
            # 使用 asyncio.wait_for 添加额外的超时保护
            completion = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text},
                    ],
                    **kwargs,
                ),
                timeout=60.0,
            )
            return completion.choices[0].message.content

        except asyncio.TimeoutError:
            # asyncio.wait_for 的超时
            raise TimeoutError(f"OpenAI API 请求超时 (90s)")
        except APITimeoutError as e:
            # OpenAI 客户端的超时
            raise TimeoutError(f"OpenAI API 超时: {str(e)}")
        except APIConnectionError as e:
            # 连接错误
            raise ConnectionError(f"连接失败: {str(e)}")
        except Exception as e:
            # 其他错误
            raise RuntimeError(f"API 请求失败: {str(e)}")
        finally:
            pass


api = OpenaiApi(app_config.openai)
