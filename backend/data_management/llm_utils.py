import json
import os
import time
import openai
from typing import Dict, Optional

import logging
logger = logging.getLogger(__name__)

def get_llm_client(scheme='openai'):
    """
    获取 OpenAI 或其他 LLM 服务的客户端

    Args:
        scheme: 客户端类型，支持 'openai' 和 'siliconflow'

    Returns:
        openai.Client: 配置好的客户端实例
    """
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL')
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        client_kwargs = {'api_key': api_key}
        if base_url:
            client_kwargs['base_url'] = base_url
            
        client = openai.OpenAI(**client_kwargs)
        logger.info(f"已成功初始化 {scheme} 客户端")
        return client
    except Exception as e:
        logger.error(f"初始化 {scheme} 客户端出错: {e}")
        raise

def llm_gen_dict(client: openai.Client, model: str, query: str, format_example: Dict, stream=False) -> Optional[Dict]:
    """
    使用 LLM 生成指定格式的 Python 字典响应

    Args:
        client: OpenAI 客户端实例
        model: 模型名称
        query: 查询内容
        format_example: 期望的字典格式示例
        stream: 是否使用流式模式

    Returns:
        dict: 生成的字典数据，失败则返回 None
    """
    logger.info("=== llm_gen_dict 入参调试信息 ===")
    logger.info(f"client: {type(client)}")
    logger.info(f"model: {model}")
    logger.info(f"query 长度: {len(query) if query else 0}")
    logger.info(f"query : {query if query else 'None'}")
    logger.info(f"stream: {stream}")
    logger.info("================================")
    
    logger.debug(f"开始生成字典，查询内容: {query}")
    logger.info(f"stream模式: {stream}")
    
    format_str = json.dumps(format_example, ensure_ascii=False, indent=2)
    prompt = f"""
请根据以下要求生成一个Python字典响应。

用户请求：
{query}

请严格按照以下格式返回Python字典（长文本用三引号）：
{format_str}

请确保输出严格的Python字典格式，不要有任何额外的文本说明。
"""

    messages = [{"role": "user", "content": prompt}]

    for retry in range(3):
        logger.info(f"第{retry+1}次尝试生成字典...")
        try:
            if not stream:
                # 非流式模式
                llm_response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                )
                response_content = llm_response.choices[0].message.content
                logger.info(f"收到的完整响应: {response_content}")
            else:
                # 流式模式
                logger.info("使用流式模式接收响应，将在完成后提取字典")
                response_content = ""
                stream_response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True
                )

                for chunk in stream_response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content_chunk = chunk.choices[0].delta.content
                        response_content += content_chunk

                logger.info(f"流式响应完成，收集到的完整内容: {response_content}")

            # 解析响应为字典
            result = parse_llm_response_to_dict(response_content)
            
            if result is not None:
                logger.info(f"第{retry+1}次尝试成功！")
                return result
            else:
                logger.warning(f"第{retry+1}次尝试失败，准备重试...")
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"第{retry+1}次发生错误: {str(e)}")
            if '429' in str(e):
                logger.warning("遇到429，等待28秒后重试...")
                time.sleep(28)
            else:
                time.sleep(2)
                
    logger.error("三次尝试均失败，返回None")
    return None

def parse_llm_response_to_dict(response_content: str) -> Optional[Dict]:
    """
    解析LLM响应内容为Python字典

    Args:
        response_content: LLM返回的响应内容

    Returns:
        dict: 解析后的字典，失败则返回 None
    """
    if not response_content:
        return None
        
    try:
        # 使用ast.literal_eval更安全地解析Python字典
        import ast
        result = ast.literal_eval(response_content.strip())
        logger.info(f"成功解析字典: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        return result if isinstance(result, dict) else None
    except SyntaxError as se:
        logger.error(f"字典解析语法错误: {str(se)}")
        # 尝试使用正则表达式提取字典
        import re
        dict_pattern = r'({[\s\S]*})'  # 更宽松的模式，可以匹配多行字典
        dict_matches = re.search(dict_pattern, response_content.strip(), re.DOTALL)
        
        if dict_matches:
            dict_str = dict_matches.group(1)
            try:
                # 尝试清理字典字符串
                cleaned_dict = re.sub(r'```python|```', '', dict_str).strip()
                import ast
                result = ast.literal_eval(cleaned_dict)
                logger.info("清理后成功解析")
                return result if isinstance(result, dict) else None
            except Exception as e2:
                logger.error(f"清理后解析仍然失败: {str(e2)}")
                return None
        else:
            logger.error(f"无法从响应中提取字典: {response_content}")
            return None
    except Exception as e:
        logger.error(f"解析响应时发生错误: {str(e)}")
        return None

