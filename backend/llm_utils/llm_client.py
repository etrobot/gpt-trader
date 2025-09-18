from __future__ import annotations
import json
import logging
from typing import Dict, Any
import openai
import os

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

def llm_gen_dict(client: openai.Client, model: str, query: str, format_example: Dict, stream: bool = False) -> Dict:
    """
    使用LLM生成符合指定格式的字典结果
    
    Args:
        client: OpenAI客户端实例
        model: 模型名称
        query: 查询内容
        format_example: 输出格式示例
        stream: 是否使用流式输出
        
    Returns:
        Dict: 解析后的字典结果
    """
    
    # 构建系统提示，强制输出为JSON格式
    system_prompt = f"""你是一个专业的加密货币分析师。请严格按照以下JSON格式输出结果，不要包含任何其他文字：

输出格式示例：
{json.dumps(format_example, ensure_ascii=False, indent=2)}

重要要求：
1. 输出必须是有效的JSON格式
2. 不要包含任何解释或额外文字
3. 分数必须是1-5的整数
4. 说明必须是中文"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            stream=stream
        )
        
        if stream:
            # 处理流式响应
            content = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content
        else:
            content = response.choices[0].message.content
        
        # 简单的JSON解析，假设LLM返回有效JSON
        result = json.loads(content)
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        # 返回默认格式
        return {}
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        return {}

def evaluate_content_with_llm(model: str, content: str, criteria_dict: Dict, category: str) -> Dict:
    """
    使用OpenAI API评估内容

    Args:
        model: 模型名称
        model: 模型名称
        content: 待评估的内容
        criteria_dict: 评估标准字典

    Returns:
        dict: 包含详细评估结果的字典，格式如下：
        {
            "overall_score": float,  # 总分
            "detailed_scores": dict,  # 各项详细分数
            "top_scoring_criterion": str,  # 最高分标准
            "top_score": float,  # 最高分数
        }
    """

    # 构建输出格式示例
    format_example = {
        "category":"category_name",
        "criteria_name_1":{"score":"1-5", "explanation":"中文评分说明"},
        "criteria_name_2":{"score":"1-5", "explanation":"中文评分说明"},
        "criteria_name_...":{"score":"1-5", "explanation":"..."},
    }
    
    criteria_text = json.dumps(criteria_dict, ensure_ascii=False, indent=2)
    query = content + f"""
按标准评估以上内容：
{criteria_text}
"""+'并添加分类名称比如“激光设备(先进制造)”，必须来自以下分类：'+category
    
    client = get_llm_client()
    # 使用 llm_gen_dict 来强约束输出为 python 字典
    result = llm_gen_dict(client, model, query, format_example, stream=False)

    # 检查result是否为None或空字典
    if not result or not isinstance(result, dict):
        logger.error(f"LLM evaluation failed, result is: {result}")
        return {
            "criteria_result": {},
            "overall_score": 0,
            "detailed_scores": {},
            "top_scoring_criterion": "评估失败",
            "top_score": 0,
        }

    # 过滤掉非评估标准的字段（如category）
    criteria_results = {k: v for k, v in result.items() 
                       if isinstance(v, dict) and 'score' in v}
    
    if not criteria_results:
        logger.error(f"No valid criteria results found in: {result}")
        return {
            "criteria_result": result,
            "overall_score": 0,
            "detailed_scores": result,
            "top_scoring_criterion": "无有效评估",
            "top_score": 0,
        }

    total_score = sum(int(v['score']) for v in criteria_results.values())/5*100/len(criteria_results)
    top_criterion = max(criteria_results.items(), key=lambda x: int(x[1]['score']))[0]
    top_score = int(max(criteria_results.items(), key=lambda x: int(x[1]['score']))[1]['score'])/5*100
    
    # 构建详细分数字典，只包含评估标准的分数
    detailed_scores = {}
    for criterion, score_data in criteria_results.items():
        detailed_scores[criterion] = int(score_data['score'])
    
    return {
        "criteria_result": result,
        "overall_score": total_score,
        "detailed_scores": detailed_scores,  # 只包含评估标准的分数
        "top_scoring_criterion": top_criterion,
        "top_score": top_score,
    }